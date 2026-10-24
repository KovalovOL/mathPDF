"""Compare browser evidence to PDF rasterization; references are QA only, not formula content."""
import argparse
import json
import math
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageChops, ImageFilter, ImageStat


def ink(image):
    return image.convert("L").point(lambda p: 255 if p<160 else 0)


def iou(a,b):
    intersection=ImageStat.Stat(ImageChops.multiply(a,b)).sum[0]/255
    union=ImageStat.Stat(ImageChops.lighter(a,b)).sum[0]/255
    return intersection/union if union else 1


def nearby_ink_coverage(a,b):
    def coverage(one,other):
        hit=ImageStat.Stat(ImageChops.multiply(one,other.filter(ImageFilter.MaxFilter(3)))).sum[0]
        total=ImageStat.Stat(one).sum[0]
        return hit/total if total else 1
    return min(coverage(a,b),coverage(b,a))


def compare(pdf_path, directory):
    result=json.loads((directory/"results.json").read_text())
    metrics=[]
    with pdfium.PdfDocument(pdf_path) as pdf:
        for case in result["cases"]:
            browser=Image.open(directory/f"{case['name']}.png").convert("RGB")
            page=pdf[case['page']-1]
            bitmap=page.render(scale=4)
            source=bitmap.to_pil().convert("RGB")
            x,y,_,_=case['bbox']
            reference=source.transform(browser.size,Image.Transform.AFFINE,(1,0,x*4,0,1,y*4),resample=Image.Resampling.BICUBIC)
            reference.save(directory/f"{case['name']}-pdf.png")
            a,b=ink(browser),ink(reference)
            metric={"name":case['name'],"page":case['page'],"size":browser.size,
                    "mean_absolute_gray_difference":round(ImageStat.Stat(ImageChops.difference(browser.convert('L'),reference.convert('L'))).mean[0],3),
                    "ink_iou":round(iou(a,b),4)}
            metric["symmetric_ink_coverage_within_1px"]=round(nearby_ink_coverage(a,b),4)
            best=(metric['ink_iou'],(0,0))
            for dx in range(-2,3):
                for dy in range(-2,3):
                    shifted=Image.new('L',b.size,0);shifted.paste(b,(dx,dy))
                    score=iou(a,shifted)
                    if score>best[0]:best=(score,(dx,dy))
            metric.update(ink_iou_within_2px=round(best[0],4),best_raster_offset=best[1])
            combined=Image.new('RGB',(browser.width,browser.height*2+12),'#d6dfd0')
            combined.paste(reference,(0,0));combined.paste(browser,(0,browser.height+12))
            combined.save(directory/f"{case['name']}-comparison.png")
            metrics.append(metric)
            bitmap.close();page.close()
    (directory/'comparison.json').write_text(json.dumps(metrics,indent=2))
    print(json.dumps(metrics,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--pdf',type=Path,default=Path('main.pdf'))
    parser.add_argument('--artifacts',type=Path,default=Path('artifacts/browser'))
    args=parser.parse_args();compare(args.pdf,args.artifacts)
