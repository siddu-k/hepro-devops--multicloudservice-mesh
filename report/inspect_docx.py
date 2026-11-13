import zipfile, re, collections
from docx import Document

path = "/mnt/c/siddu/VOICE DESK/devops-project-5/report/DevOps-Project-5-Report.docx"
doc = Document(path)

h1 = [p.text for p in doc.paragraphs if p.style.name == "Heading 1"]
h2 = [p.text for p in doc.paragraphs if p.style.name == "Heading 2"]
h3 = [p.text for p in doc.paragraphs if p.style.name == "Heading 3"]
print("H1:", len(h1))
for t in h1: print("   ", t)
print("H2:", len(h2), "H3:", len(h3))
print("tables:", len(doc.tables), "inline shapes:", len(doc.inline_shapes))

with zipfile.ZipFile(path) as z:
    media = [n for n in z.namelist() if n.startswith("word/media/")]
print("media files:", len(media))

caps = [p.text for p in doc.paragraphs if p.text.startswith("Figure ")]
print("captions:", len(caps))
nums = [int(re.match(r"Figure (\d+)\.", c).group(1)) for c in caps if re.match(r"Figure (\d+)\.", c)]
print("numbers:", nums)
print("duplicates:", [n for n, c in collections.Counter(nums).items() if c > 1])
print("gaps:", [i for i in range(1, max(nums)+1) if i not in nums])

words = sum(len(p.text.split()) for p in doc.paragraphs)
for t in doc.tables:
    for row in t.rows:
        for c in row.cells:
            words += len(c.text.split())
print("approx words:", words)
print("first captions:")
for c in caps[:5]: print("   ", c[:110])