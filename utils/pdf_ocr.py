"""Bounded raster OCR using the Surya models already owned by Parser."""
import math
import hashlib

MAX_PIXELS = 12_000_000
MIN_CONFIDENCE = .85


class EmptyRasterRegion(ValueError):
    """The displayed region has no visible contrast to transcribe."""


class RasterOCR:
    def __init__(self, converter):
        self.models = getattr(converter, 'artifact_dict', {})

    def __call__(self, page, box):
        import pymupdf
        from PIL import Image
        recognition = self.models.get('recognition_model')
        detection = self.models.get('detection_model')
        if recognition is None or detection is None:
            raise ValueError('Existing raster OCR models unavailable')
        # Stored source boxes use unrotated PDF coordinates; pixmaps use the
        # displayed page. Rendering resolves clipping and ignores hidden objects.
        display = pymupdf.Rect(box)*page.rotation_matrix
        display &= page.rect
        if display.is_empty or display.is_infinite:
            raise ValueError('OCR region has invalid visible bounds')
        scale = min(2.5, math.sqrt(MAX_PIXELS/max(1, display.get_area())))
        pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=display, alpha=False)
        image = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
        if all(hi-lo < 2 for lo,hi in image.getextrema()):
            image.close()
            raise EmptyRasterRegion('Rendered region is visually uniform')
        image_hash = hashlib.sha256(image.tobytes()).hexdigest()
        try:
            results = recognition(images=[image], det_predictor=detection,
                recognition_batch_size=8, detection_batch_size=1,
                sort_lines=False, math_mode=True, return_words=True)
        finally:
            image.close()
        if len(results) != 1:
            raise ValueError('OCR returned a different number of regions')
        lines = []
        # Use actual raster dimensions (rounding may differ on the two axes).
        for line in results[0].text_lines:
            rect = pymupdf.Rect(line.bbox)
            mapped = pymupdf.Rect(display.x0+rect.x0*display.width/pix.width,
                display.y0+rect.y0*display.height/pix.height,
                display.x0+rect.x1*display.width/pix.width,
                display.y0+rect.y1*display.height/pix.height)*page.derotation_matrix
            confidences = [float(line.confidence or 0)]
            # A confidently read sentence must not conceal an uncertain number.
            confidences.extend(float(word.confidence or 0) for word in (getattr(line,'words',None) or [])
                               if any(c.isdigit() for c in word.text))
            lines.append({'text':line.text, 'bbox':list(mapped),
                          'confidence':min(confidences)})
        return {'lines':lines, 'image_hash':image_hash, 'engine':'surya_raster',
                'pixels':[pix.width, pix.height], 'rotation':page.rotation}
