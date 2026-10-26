"""Sample-only verdict schemas and recovery within the shared preparation budget."""
import json

from jsonschema import Draft202012Validator


class VerificationInterrupted(Exception):
    """Honor cooperative stop before a format-recovery request."""


def verdict_schema(claim):
    string = {'type': 'string'}
    strings = {'type': 'array', 'items': string}
    boolean = {'type': 'boolean'}
    span = {'type': 'object', 'additionalProperties': False,
            'properties': {'quote': string, 'evidence_ids': strings, 'supported': boolean},
            'required': ['quote', 'evidence_ids', 'supported']}
    properties = {'supported': boolean, 'error_types': strings, 'reason': string,
                  'corrected_text': string, 'coverage': {'type': 'array', 'items': span},
                  'relationships_supported': boolean, 'covered_required_evidence_ids': strings,
                  'necessary_information_preserved': boolean}
    if (claim or {}).get('editorial_revision'):
        properties['editorial_information_preserved'] = boolean
    if (claim or {}).get('completion_origin'):
        properties.update(completion_relevant=boolean, completion_non_redundant=boolean)
    return {'type': 'object', 'additionalProperties': False,
            'properties': properties, 'required': list(properties)}


def verdict_prompt(prompt, schema):
    return prompt + ('\nOUTPUT CONTRACT (verification verdict, never the input claim):\n'
                     + json.dumps(schema, ensure_ascii=False, sort_keys=True)
                     + '\nReturn a verdict for the exact supplied claim. Unknown support is false. '
                     'Use empty arrays/strings where appropriate, never omit required fields. '
                     'Do not infer scientific support from conformance to this schema.')


def request_verdict(journal, agent, prompt, schema):
    """No coercion, semantic retry, provider fallback or independent free allowance."""
    from utils.langgraph_utils import extract_json, ChatOpenAI
    previous = getattr(agent, 'response_json_schema', None)
    model = getattr(agent, 'model', None)
    bound = bool(getattr(agent, 'request_policy', None)) and isinstance(model, ChatOpenAI)
    if bound:
        # bind() returns a RunnableBinding, so the unchanged shared step wrapper
        # preserves this explicit format instead of binding its default JSON mode.
        agent.model = model.bind(response_format={'type': 'json_schema', 'json_schema': {
            'name': 'sample_verification_verdict', 'strict': True, 'schema': schema}})
    agent.response_json_schema = schema
    try:
        for index in (0, 1):
            stop = journal.state.get('_force_stop_requested')
            if stop and stop():
                raise VerificationInterrupted()
            content = journal.request(index, agent, prompt)
            try:
                parsed = extract_json(content)
                journal.write(f'parsed_{index:02d}.json', parsed=parsed)
                errors = list(Draft202012Validator(schema).iter_errors(parsed))
                if errors:
                    # Report paths and failed constraints, not invented/default verdicts.
                    paths = [f"{'.'.join(map(str, e.absolute_path)) or 'verdict'}:{e.validator}" for e in errors[:12]]
                    raise ValueError('Invalid sample verification verdict: ' + ', '.join(paths))
            except (ValueError, TypeError) as exc:
                journal.write(f'validation_{index:02d}.json', status='rejected', error=str(exc))
                if index:
                    raise
                prompt += ('\nThe previous response violated the output contract. Re-evaluate the SAME '
                           'claim and evidence and return only the required verification verdict. '
                           'Do not change the input claim or treat the response below as evidence.\n'
                           + str(exc) + '\nUNTRUSTED PREVIOUS RESPONSE:\n' + content)
                continue
            journal.write('verdict.json', status='valid_structure', response_index=index, verdict=parsed)
            return parsed, content
    finally:
        if bound:
            agent.model = model
        if previous is None:
            del agent.response_json_schema
        else:
            agent.response_json_schema = previous
