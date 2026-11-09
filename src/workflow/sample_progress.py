"""Concise terminal progress; verbose details remain in the existing run log."""
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import sys
import threading
import time

from rich.console import Console
from rich.text import Text
from utils.src.logging_utils import observe_progress


STAGES = {
    'parser': ('Parser', '加载解析模型、提取 PDF 并整理论文'),
    'curator': ('Curator', '规划模块、计算正文框并写作'),
    'color_agent': ('Color', '提取图片配色并选择海报颜色'),
    'title_designer': ('Title', '设计模块标题样式'),
    'joint_preparation': ('Layout', '测量布局，按需协调高度与容量'),
    'layout_optimizer': ('Compile', '编译最终布局并校验冻结内容'),
    'font_agent': ('Font', '选择关键词并应用文字样式'),
    'layout_preflight': ('Preflight', '检查文字与布局边界'),
    'renderer': ('Renderer', '导出可编辑 PPTX 和 PNG'),
    'render_fit_audit': ('RenderFit', '核对实际渲染文字与碰撞'),
    'critic': ('Critic', '依次评价科学内容与视觉质量'),
    'publish': ('Save', '保存样本、评分和诊断文件'),
    'run': ('Run', '初始化并检查运行状态'),
}
OPERATIONS = {
    'editorial_proofreading': '校对 PDF 提取文字',
    'editorial_metadata': '整理标题与作者',
    'editorial_abt': '整理研究叙事',
    'editorial_sections': '整理论文章节',
    'editorial_visuals': '整理图表与图注',
    'editorial_curator': '规划模块与图表归属',
    'editorial_writer': '按实际正文框写作',
    'editorial_palette': '分析图片配色',
    'editorial_balancer': '执行单轮容量编辑',
    'editorial_content_critic': '评价科学内容与模块依赖',
    'editorial_visual_critic': '评价视觉质量与阅读顺序',
    'critic_content': '评价科学内容与模块依赖',
    'critic_visual': '评价视觉质量与阅读顺序',
    'font_agent': '提取强调关键词',
}


def format_event(event):
    """Plain callback text for WebUI and older event consumers."""
    kind = event.get('type')
    number = event.get('iteration')
    lead = f'Sample {number} | ' if number is not None else ''
    if kind == 'task_inputs':
        return f'{lead}Starting full poster task from PDF, Logos and generation parameters'
    if kind == 'paper_checkpoint_reused':
        return f'{lead}Restoring this task\'s completed paper preparation'
    if kind == 'paper_cache_reused':
        return f"{lead}Explicit paper cache reused | {event.get('source_run_id')} | {event.get('source_sample_id') or 'single source'}"
    if kind == 'family_frozen':
        return f"{lead}Family frozen before module planning | {event.get('family')}"
    if kind == 'sample':
        return f"{lead}{event.get('attempt')} | {event.get('family')}"
    if kind == 'sample_saved':
        r = event['result']
        action = 'recorded; no poster exported' if 'poster_id' in r and not r['poster_id'] else 'saved'
        location = f" | 保存位置：{event['poster_directory']}" if r.get('poster_id') and event.get('poster_directory') else ''
        return f"{r['sample_id']} {action} | {r['status']} | score {r['score']} | {r.get('grouping', 'unclassified')}{location}"
    if kind == 'stage_start':
        return f"{lead}{event['stage']} started"
    if kind == 'stage_done':
        return f"{lead}{event['stage']} {event.get('outcome', 'finished')} ({event.get('elapsed', 0):.2f}s)"
    if kind == 'layout_detail':
        details = ' | '.join(f'{k} {v}' for k, v in event.items()
                             if k not in {'type', 'run_id', 'iteration', 'planned_samples', 'label'})
        return f"{lead}{event.get('label', 'layout')} | {details}"
    if kind == 'layout_fit_retry':
        return f"{lead}Fit retry after {event.get('family')} | {event.get('reason')}"
    if kind == 'curation_reused':
        return f"{lead}Reusing this sample's content plan (revision {event.get('revision')}); no Curator request"
    if kind == 'curation_repair':
        return f"{lead}One charged content-plan repair | {event.get('reason')}"
    if kind == 'content_completion_rollback':
        return f'{lead}Restoring same-attempt completion baseline and checking again'
    if kind == 'error':
        return f"{lead}Error in {event.get('stage')}: {event.get('message')}"
    if kind == 'finished':
        return f"Run {event.get('run_id')} | {event.get('status')}"
    return lead + str(event.get('message') or kind)


class SampleProgressReporter:
    def __init__(self, log_path, terminal=None, *, verbose=False, heartbeat_seconds=15):
        self.terminal = terminal if terminal is not None else sys.stdout
        self.log_path = log_path
        self.verbose = verbose
        self._detail_stream = getattr(self.terminal, 'log_stream', None)
        self.console = Console(file=self.terminal, highlight=False)
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._thread = None
        self._stage = 'run'
        self._stage_started = self._run_started = time.perf_counter()
        self._sample_started = None
        self._number = self._total = None
        self._active = True
        self._operation = None
        self._request = None
        self._local_action = None
        self._heartbeat_seconds = heartbeat_seconds

    def __enter__(self):
        self._stack = ExitStack()
        # Raw third-party chatter is retained, but does not drown out progress.
        # A standalone reporter without a tee never swallows stdout/stderr.
        if self._detail_stream is not None and not self.verbose:
            self._stack.enter_context(redirect_stdout(self._detail_stream))
            self._stack.enter_context(redirect_stderr(self._detail_stream))
        self._stack.enter_context(observe_progress(self.emit))
        self._thread = threading.Thread(target=self._heartbeat, daemon=True)
        self._thread.start()
        self._line(f'详细日志：{self.log_path}', elapsed=0)
        return self

    def __exit__(self, *_exc):
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
        self._stack.close()

    def _detail(self, text):
        if self._detail_stream is not None:
            print(text, file=self._detail_stream, flush=True)

    def _line(self, message, *, level='info', elapsed=None, stage=None):
        stage = stage or self._stage
        label = STAGES.get(stage, (stage.replace('_', ' ').title(), ''))[0]
        elapsed = time.perf_counter() - self._stage_started if elapsed is None else elapsed
        sample = f'{self._number}/{self._total or "?"}' if self._number is not None else '-'
        color = {'info': 'cyan', 'success': 'green', 'warning': 'yellow', 'error': 'red'}[level]
        text = Text(f'[ {label:^12} ]', style=f'bold {color}')
        text.append(f' [样本 {sample}] [阶段 {elapsed:7.1f}s] ', style='dim')
        text.append(' '.join(str(message).splitlines()))
        self.console.print(text, soft_wrap=True)

    def _heartbeat(self):
        while not self._stop.wait(self._heartbeat_seconds):
            self.heartbeat()

    def heartbeat(self):
        """Only report live work, with monotonic time; never invent a percentage."""
        with self._lock:
            if not self._active:
                return
            current = self._request or self._operation
            if current:
                action = f"{current['label']} | 已等待 {time.perf_counter() - current['started']:.1f}s"
            else:
                action = self._local_action or STAGES.get(self._stage, ('', self._stage))[1]
            self._line(f'进行中 · {action}')

    def emit(self, event):
        with self._lock:
            self._emit(event)

    def _emit(self, event):
        kind = event.get('type')
        now = time.perf_counter()
        if event.get('iteration') is not None:
            self._number = event['iteration']
        if event.get('planned_samples') is not None:
            self._total = event['planned_samples']
        if kind == 'agent_log':
            level = event['level'].lower()
            message = event['message']
            if event['agent'] == 'parser' and message in {'converting pdf to raw text', 'extracting assets'}:
                self._local_action = {'converting pdf to raw text': '正在提取 PDF 文字与版面',
                                      'extracting assets': '正在提取图表资产'}[message]
                if not self.verbose:
                    self._line(self._local_action)
            if self.verbose or level in {'warning', 'error'}:
                location = f" [{event['location']}]" if self.verbose and event.get('location') else ''
                self._line(f"{event['agent']}{location} · {message}",
                           level=level if level in {'success', 'warning', 'error'} else 'info')
            else:
                self._detail(f"[{event['agent']}] [{event.get('location') or '-'}] {message}")
            return
        if kind == 'layout_detail':
            label = event.get('label', '')
            self._local_action = f'布局测量 · {label}' if label.endswith('started') else '处理布局测量结果'
            if self.verbose:
                self._line(format_event(event))
            else:
                self._detail(format_event(event))
            return
        if kind == 'operation_start':
            label = OPERATIONS.get(event['operation'], event['operation'])
            self._operation = {'label': label, 'started': now, 'requests': 0}
            self._line(f'开始 · {label}')
            return
        if kind in {'operation_done', 'operation_failed'}:
            operation = self._operation
            label = OPERATIONS.get(event['operation'], event['operation'])
            failed = kind == 'operation_failed'
            message = f"{'失败' if failed else '响应校验完成'} · {label} | 操作用时 {event['elapsed']:.1f}s"
            if failed:
                message += f" | {event.get('message', '')}"
            self._line(message, level='error' if failed else 'success')
            if operation and not operation['requests'] and not failed:
                self._detail('No physical model request observed; existing response or injected offline implementation.')
            self._operation = self._request = None
            return
        if kind == 'model_request':
            action = event['event']
            attempt = event.get('attempt', 1)
            label = (self._operation or {}).get('label') or OPERATIONS.get(event['agent'], event['agent'])
            if action == 'request_start':
                self._request = {'label': f'{label}（模型请求 {attempt}）', 'started': now}
                if self._operation:
                    self._operation['requests'] += 1
                if not self._operation or attempt > 1 or self._operation['requests'] > 1:
                    self._line(f'请求 · {label} | 尝试 {attempt}' +
                               (f" | 本操作实际请求 {self._operation['requests']}" if self._operation else ''))
            else:
                seconds = event.get('elapsed_seconds', 0)
                if action == 'request_finished':
                    finish = event.get('finish_reason') or 'unknown'
                    truncated = str(finish).lower().split('.')[-1] in {'length', 'max_tokens'}
                    level = 'error' if truncated else 'info'
                    message = f"{'输出截断' if truncated else '响应返回'} · {label} | 请求 {seconds:.1f}s | {finish}"
                    if event.get('input_tokens') is not None and event.get('output_tokens') is not None:
                        message += f" | tokens {event['input_tokens']}→{event['output_tokens']}"
                    # Successful nested transport details stay in run.log; the
                    # operation's completion also includes local validation.
                    if self._operation and not truncated and not self.verbose:
                        self._detail(message)
                    else:
                        self._line(message, level=level)
                else:
                    retry = action == 'request_retry'
                    self._line(f"{'重试等待（2s）' if retry else '请求失败'} · {label} | 尝试 {attempt} | 请求 {seconds:.1f}s | {event.get('error_type')}",
                               level='warning' if retry else 'error')
                self._request = None
            return
        if kind == 'task_inputs':
            self._sample_started = now
            self._operation = self._request = self._local_action = None
            self._stage, self._stage_started, self._active = 'run', now, True
            self._line('开始 · 从 PDF、Logo 和参数生成完整海报样本', elapsed=0)
        elif kind == 'stage_start':
            self._stage, self._stage_started, self._active = event['stage'], now, True
            self._operation = self._request = None
            self._local_action = None
            self._line(f"开始 · {STAGES.get(self._stage, ('', self._stage))[1]}", elapsed=0)
        elif kind == 'stage_done':
            warnings = {'evaluation_failed': '评分失败/不完整',
                        'layout_defects': '完成（存在布局缺陷）', 'underfilled': '完成（仍有欠填）',
                        'partial': '完成（核验不完整）', 'unavailable': '核验不可用',
                        'failed': '核验未通过'}
            outcome = event.get('outcome')
            suffix = f" | {event['detail']}" if event.get('detail') else ''
            self._line(warnings.get(outcome, '完成') + suffix,
                       elapsed=event.get('elapsed', now-self._stage_started),
                       level='warning' if outcome in warnings else 'success')
            self._active = False
            self._operation = self._request = None
        elif kind == 'error':
            self._line(format_event(event), level='error')
            self._active = False
            self._operation = self._request = None
        elif kind == 'sample_saved':
            elapsed = f' | 本次样本 {now-self._sample_started:.1f}s' if self._sample_started is not None else ''
            result = event['result']
            self._line(format_event(event) + elapsed,
                       level='success' if result['status'] == 'scored' else 'warning', stage='publish')
            self._active = False
        elif kind == 'run_summary':
            r = event['run']
            self._line(f"{r['status']} | 任务 {r['finalized_samples']}/{r['planned_samples']} | 已导出 {r['rendered_samples']} | 已评分 {r['scored_samples']} | 失败 {r['failed_samples']} | 本次运行 {now-self._run_started:.1f}s | 结果：{event['output_dir']} | 日志：{self.log_path}",
                       stage='run', elapsed=now-self._run_started,
                       level='success' if r['status'] == 'COMPLETED' and not r['failed_samples'] else 'warning')
            self._active = False
        elif kind == 'finished':
            self._active = False
            self._detail(format_event(event))
        else:
            self._line(format_event(event))

    def write_traceback(self, text):
        with self._lock:
            if self.verbose or self._detail_stream is None:
                print(text, file=self.terminal, flush=True)
            else:
                self._detail(text)
                self._line(f'完整异常堆栈已保存：{self.log_path}', level='error')
