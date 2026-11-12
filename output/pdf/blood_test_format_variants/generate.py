"""Run from repository root using Python with reportlab, pdfplumber and Pillow."""
from pathlib import Path
import copy, json, zipfile, re
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.utils import simpleSplit
import pdfplumber
from PIL import Image, ImageDraw
OUT=Path(__file__).resolve().parent
BASE=OUT.parent/'blood_test_samples/sample_10_mixed_precision.expected.json'
source=json.loads(BASE.read_text())
rows=source['results']
INK='#173442'; MUTED='#526775'; LIGHT='#eef3f5'; BORDER='#ced9df'
def text(c,x,y,s,size=9,bold=False,color=INK):
 c.setFillColor(HexColor(color));c.setFont('Helvetica-Bold' if bold else 'Helvetica',size);c.drawString(x,y,str(s))
def rule(c,x,y,w):
 c.setStrokeColor(HexColor(BORDER));c.setLineWidth(.5);c.line(x,y,x+w,y)
def rect(c,x,y,w,h,color):
 c.setFillColor(HexColor(color));c.rect(x,y,w,h,stroke=0,fill=1)
def header(c,w,h,title,subtitle):
 rect(c,0,h-70,w,70,INK);text(c,28,h-29,title,18,True,'#ffffff');text(c,28,h-49,subtitle,9,False,'#d8e5eb')
 text(c,28,h-92,'Synthetic Patient, 010 | ID: SYN-010 | DOB: 01/01/1970 | Age: 55 | Sex: Female',8)
 text(c,28,h-106,'Specimen: SYN-2025-010 | Account: SYN900010 | Fasting: Not Given',8)
 text(c,28,h-120,'Collected: 01/21/2025 | Received: 01/21/2025 | Reported: 01/22/2025',8)
 text(c,28,h-134,'Ordered items: CD4/CD8 Ratio Profile',8,True)
def footer(c,w,page,total):
 rule(c,28,46,w-56);text(c,28,32,'SYNTHETIC TEST REPORT - NOT FOR CLINICAL USE',7,True)
 text(c,w-95,32,f'Page {page} of {total}',7)
 text(c,28,20,'Laboratory codes: 01 / 02 (synthetic). Previous result/date: blank throughout.',6.5,False,MUTED)
def lab(r):return r['lab_code'] or ''
def flag(r,short=False):return (r['flag'][0] if short else r['flag']) if r['flag'] else ''
def ref(r):return r['reference_interval']['text'] or ''
def colored(r):return '#a53b27' if r['flag'] else INK

def compact(path):
 w,h=792,612;c=canvas.Canvas(str(path),pagesize=(w,h));c.setTitle('Format variant 01: compact landscape')
 header(c,w,h,'Clinical results | compact view','Landscape table with reordered fields and abbreviated headings')
 xs=[28,260,383,485,565,649];y=452
 rect(c,28,y-6,736,20,INK)
 for x,s in zip(xs,['Test / lab','Ref. int.','UOM','Flg','Res.','Prev. / date']):text(c,x+6,y,s,8,True,'#ffffff')
 y-=17
 for i,r in enumerate(rows):
  if i%2==0:rect(c,28,y-4,736,12.3,LIGHT)
  text(c,34,y,r['test_name'],7.7)
  if lab(r):text(c,237,y+2,lab(r),5.5)
  for x,s in [(266,ref(r)),(389,r['unit'] or ''),(491,flag(r)),(571,r['value_text'])]:text(c,x,y,s,7.7,x in [491,571] and bool(r['flag']),colored(r) if x in [491,571] else INK)
  y-=12.3
 text(c,28,91,'Immature Granulocytes note: Available upon request',7)
 text(c,28,78,'Blank flags mean no printed flag; blank reference intervals remain unspecified.',7,False,MUTED)
 footer(c,w,1,1);c.save()

def card(c,x,top,r):
 width=268;height=60
 rect(c,x,top-height,width,height,LIGHT)
 lines=simpleSplit(r['test_name'],'Helvetica-Bold',9,90)
 for i,s in enumerate(lines):text(c,x+9,top-14-i*10,s,9,True)
 if lab(r):text(c,x+9,top-35,'Lab '+lab(r),6.5,False,MUTED)
 text(c,x+148,top-17,r['value_text'],15,True,colored(r))
 text(c,x+212,top-17,flag(r),8,True,colored(r))
 text(c,x+148,top-31,'Unit: '+(r['unit'] or ''),7)
 text(c,x+9,top-48,'Reference: '+ref(r),7)
 if r['note']:text(c,x+9,top-57,r['note'],6.5,False,MUTED)
def cards(path):
 w,h=612,792;c=canvas.Canvas(str(path),pagesize=(w,h));c.setTitle('Format variant 02: sectioned cards')
 groups=[ [('CD4 / CD8 measurements',rows[:5]),('Red cell measurements',rows[6:13])], [('White cells and differential',[rows[5]]+rows[14:]),('Platelets',[rows[13]])] ]
 for page,sections in enumerate(groups,1):
  header(c,w,h,'Laboratory results | sectioned cards','Labeled result blocks, wrapped names and reordered clinical sections')
  top=638
  for title,rr in sections:
   text(c,28,top,title,10,True);top-=10
   for i,r in enumerate(rr):card(c,28+(i%2)*284,top-(i//2)*66,r)
   top-=((len(rr)+1)//2)*66+20
  footer(c,w,page,2);c.showPage()
 c.save()

def dense(path):
 w,h=612,792;c=canvas.Canvas(str(path),pagesize=(w,h));c.setTitle('Format variant 03: continued multipage report')
 # Force a page break inside the red-cell block; repeated headers are intentional.
 for page,rr in enumerate([rows[:10],rows[10:]],1):
  header(c,w,h,'RESULT REGISTER | '+('CONTINUED' if page==2 else 'FINAL'),'CD4/CD8 Ratio Profile - continued table with short flags and nested reference lines')
  text(c,28,632,'Legend: H = High; L = Low; blank = no printed flag.',8,True)
  text(c,28,619,'Reference intervals appear beneath current values. Prior columns are intentionally blank.',7,False,MUTED)
  rect(c,28,594,556,17,INK)
  for x,s in [(34,'TEST / LAB'),(302,'CURRENT / REFERENCE'),(436,'UNIT'),(508,'FLAG'),(545,'PRIOR')]:text(c,x,600,s,6.7,True,'#ffffff')
  top=586
  for r in rr:
   text(c,34,top,r['test_name'],8,True)
   if lab(r):text(c,252,top,lab(r),6.5)
   text(c,302,top,r['value_text'],8,True,colored(r));text(c,436,top,r['unit'] or '',7.5)
   text(c,510,top,flag(r,True),8,True,colored(r))
   text(c,302,top-11,'Ref: '+ref(r),7,False,MUTED)
   if r['note']:text(c,34,top-11,r['note'],7,False,MUTED)
   rule(c,28,top-16,556);top-=29
  if page==1:text(c,28,top-10,'Table continues on next page.',8,True)
  footer(c,w,page,2);c.showPage()
 c.save()

manifest=[]
for i,(slug,description,fn,pages) in enumerate([
 ('compact_landscape','Landscape table; Test / Range / Units / Flag / Result / Previous',compact,1),
 ('sectioned_cards','Sectioned cards; wrapped test names; changed display order',cards,2),
 ('dense_multipage','Continued multipage table; repeated headers; nested reference lines; H/L flags',dense,2)
],1):
 stem=f'format_{i:02}_{slug}';data=copy.deepcopy(source)
 data.update(sample_id=f'format_{i:02}',source_pdf=stem+'.pdf',scenario=description)
 # Entire normalized clinical payload is deliberately identical to the baseline.
 assert data['results']==source['results']
 (OUT/(stem+'.expected.json')).write_text(json.dumps(data,indent=2)+'\n')
 fn(OUT/(stem+'.pdf'))
 manifest.append(dict(sample_id=data['sample_id'],description=description,pdf=stem+'.pdf',expected_json=stem+'.expected.json',pages=pages,result_count=26,baseline_sample='sample_10',flag_normalization={'H':'High','L':'Low'} if i==3 else {}))
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')

# Independent checks use extracted page coordinates to associate names with results.
validation=[];thumbs=[]
review=Path('/private/tmp/blood_format_review');review.mkdir(exist_ok=True)
for item in manifest:
 checked=[]
 with pdfplumber.open(OUT/item['pdf']) as pdf:
  assert len(pdf.pages)==item['pages']
  assert all(p.extract_text() for p in pdf.pages)
  for r in rows:
   matches=[]
   for p in pdf.pages:
    # pdfplumber search uses the actual text layer, including wrapped card titles.
    namepattern=r'\s+'.join(map(re.escape,r['test_name'].split()))
    for m in p.search(namepattern+r'(?![A-Za-z(]|\s*\(Absolute\))',regex=True):
     # Exclude note occurrences or headings: restrict to the test-name area.
     if m['x0']<299 and m['top']>140:matches.append((p,m))
   # Card titles may be in the right column.
   if item['sample_id']=='format_02':
    matches=[]
    for p in pdf.pages:
     for box in p.rects:
      if abs(box['width']-268)>1 or abs(box['height']-60)>1:continue
      title=p.crop((box['x0']+8,box['top']+3,box['x0']+120,box['top']+29)).extract_text() or ''
      if ' '.join(title.split())==r['test_name']:
       matches.append((p,dict(x0=box['x0']+9,top=box['top']+7,bottom=box['top']+27)))
   if r['test_name']=='Immature Granulocytes':
    matches=[(p,m) for p,m in matches if not (item['sample_id']=='format_01' and m['top']>500)]
   assert len(matches)==1,(item['sample_id'],r['test_name'],len(matches))
   p,m=matches[0]
   if item['sample_id']=='format_02':
    x=28 if m['x0']<300 else 312
    # Name baseline is card top minus 14pt; include reference/note lines too.
    top=m['top']-8
    clip=p.crop((x,top,x+268,min(p.height,top+61)))
   elif item['sample_id']=='format_01':clip=p.crop((28,m['top']-2,764,m['bottom']+3))
   else:clip=p.crop((28,m['top']-2,584,m['top']+26))
   extracted=clip.extract_text()
   assert r['value_text'] in extracted.split(),(item['sample_id'],r['test_name'],extracted)
   if r['unit']:assert r['unit'] in extracted,(r,extracted)
   if ref(r):assert ref(r) in extracted,(r,extracted)
   if r['note']:assert r['note'] in extracted or (item['sample_id']=='format_01' and r['note'] in p.extract_text())
   if r['flag']:assert flag(r,item['sample_id']=='format_03') in extracted.split(),(r,extracted)
   checked.append(r['test_name'])
  for n,p in enumerate(pdf.pages,1):
   path=review/f'{item["sample_id"]}_page{n}.png';p.to_image(resolution=115).save(path)
   im=Image.open(path).convert('RGB');im.thumbnail((400,520));thumbs.append((im,f'{item["sample_id"]} / page {n}'))
 validation.append(dict(sample_id=item['sample_id'],page_count=len(pdf.pages),selectable_text=True,verified_result_count=len(checked),normalized_results_identical_to_baseline=True))
(OUT/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
contact=Image.new('RGB',(400*len(thumbs),550),'#d8dfe3');draw=ImageDraw.Draw(contact)
for i,(im,label) in enumerate(thumbs):contact.paste(im,(i*400,0));draw.text((i*400+8,530),label,fill='black')
contact.save(review/'contact.png')
(OUT/'README.md').write_text('''# Blood report formatting variants

Three selectable-text PDFs using exactly the same 26 normalized results and patient metadata as sample_10_mixed_precision from the original fixture set. These isolate layout handling from value variation. All are fictional software fixtures.

## Included layouts
1. Compact landscape: one page; reordered columns, abbreviated headings, row shading.
2. Sectioned cards: two pages; labeled blocks rather than a table; wrapped names; clinical sections change display order.
3. Dense multipage: two pages; deliberate page break inside red-cell results, repeated headers/footers, reference intervals below values, short H/L flags.

## Expected JSON
Each PDF has a matching `.expected.json`, using the original schema. Only fixture identifiers, scenario and source filename differ from the baseline. All 26 result objects, including precision, units, ranges, notes and flags, are identical. Match results by exact test name rather than display order: the cards reorder sections. Normalize H to High and L to Low. A blank flag is null; do not infer flags from formatting alone. Blank reference intervals are null, distinct from `Not Estab.`. Preserve zeros and printed decimal precision in `value_text`. Dates normalize to ISO format. Prior result/date are blank/null throughout. Lab codes are separate from test names. Fixture/scenario metadata and derived `range_status` are not fields that must appear in the PDF.

`manifest.json` indexes files and layout expectations. `validation.json` records PDF text extraction checks against all 78 result instances and unchanged baseline results. These checks verify fixture construction, not the application's parser accuracy. All five pages were rendered for visual review.

## Deferred OCR round
Future work: image-only scanned PDFs, modest rotation/skew, reduced resolution and scan noise. Keep the same underlying result data and expected JSON to isolate OCR effects. No scanned or skewed variant is included in this batch.

## Reproduce
Run `generate.py` from the repository root with Python containing reportlab, pdfplumber and Pillow. The original sample_10 expected JSON must remain at the sibling blood_test_samples path. Outputs are written beside the generator. Temporary review PNGs go to /private/tmp/blood_format_review.
''')
archive=OUT.parent/'blood_test_format_variants.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for f in sorted(OUT.iterdir()):z.write(f,'blood_test_format_variants/'+f.name)
print(json.dumps(validation,indent=2));print(archive)
