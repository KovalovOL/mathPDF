"""Audit extraction coverage without declaring formulas verified."""
import argparse
import json
from pathlib import Path
from formula_lab.extract import PdfSource
from formula_lab.models import TextNode


def scan(path: Path, output: Path):
    source=PdfSource(path,Path('.formula-lab'))
    pages=[];fonts=set();total=0
    for number in range(1,source.page_count+1):
        page=source.page(number)
        fonts.update(f.id for f in page.fonts)
        total+=sum(isinstance(n,TextNode) for n in page.nodes)
        pages.append({'page':number,'candidates':len(page.candidates),'warnings':page.warnings,
                      'unsupported_graphic_regions':len(page.unsupported_regions),
                      'font_warnings':[f.name+': '+f.warning for f in page.fonts if f.warning]})
    summary={'document_sha256':source.sha256,'pages':source.page_count,'text_nodes':total,
             'fonts':len(fonts),'candidates':sum(p['candidates'] for p in pages),
             'unsupported_graphic_regions':sum(p['unsupported_graphic_regions'] for p in pages),
             'pages_with_warnings':[p for p in pages if p['warnings'] or p['font_warnings']]}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps({'summary':summary,'pages':pages},indent=2))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--pdf',type=Path,default=Path('main.pdf'))
    parser.add_argument('--output',type=Path,default=Path('artifacts/scan.json'))
    args=parser.parse_args();scan(args.pdf,args.output)
