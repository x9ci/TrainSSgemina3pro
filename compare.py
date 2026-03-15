import docx

def get_text(filename):
    doc = docx.Document(filename)
    return '\n'.join([p.text for p in doc.paragraphs if p.text.strip() != ''])

sclass_text = get_text('trancom/sclass.docx')
zzzzzz_text = get_text('trancom/zzzzzz.docx')
bbbbbbbbbbb_text = get_text('trancom/bbbbbbbbbbb.docx')

print(f"sclass paragraphs: {len(sclass_text.splitlines())}")
print(f"zzzzzz paragraphs: {len(zzzzzz_text.splitlines())}")
print(f"bbbbbbbbbbb paragraphs: {len(bbbbbbbbbbb_text.splitlines())}")
