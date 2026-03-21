import re
c = open('app/routes/categories.py', encoding='utf-8-sig').read()

# Ana dict tanımları
for m in re.finditer(r'^[A-Z_]+ = \{', c, re.M):
    print(m.start(), repr(c[m.start():m.start()+40]))

print()
# KATEGORILER = { nerede başlıyor, nerede bitiyor?
kat_start = c.find('KATEGORILER = {')
print(f"KATEGORILER starts at: {kat_start}")

# Sonrasını parse et - brace sayarak kapanışı bul
depth = 0
in_string = False
string_char = None
pos = kat_start
for i, ch in enumerate(c[kat_start:], kat_start):
    if in_string:
        if ch == string_char and c[i-1] != '\\':
            in_string = False
    else:
        if ch in ('"', "'"):
            in_string = True
            string_char = ch
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                print(f"KATEGORILER ends at: {i}")
                print(f"Next 100 chars: {repr(c[i:i+100])}")
                break
