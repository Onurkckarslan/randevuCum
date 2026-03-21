c = open('app/templates/business/dashboard.html', encoding='utf-8').read()

old = """  window.shareInstagram = function() {
    copyText(bizUrl);
    // Instagram uygulamasını aç (kullanıcı hikaye/chat seçer)
    window.location.href = "instagram://";
    setTimeout(function() {
      window.location.href = "https://www.instagram.com/";
    }, 2500);
    document.getElementById("igModal").classList.add("show");
  };"""

new = """  window.shareNative = function() {
    if (navigator.share) {
      navigator.share({
        title: "Randevu Linkim",
        text: "Online randevu icin: " + bizUrl,
        url: bizUrl,
      }).catch(function() {});
    } else {
      copyText(bizUrl);
      alert("Link kopyalandi: " + bizUrl);
    }
  };"""

if old in c:
    c = c.replace(old, new)
    open('app/templates/business/dashboard.html', 'w', encoding='utf-8').write(c)
    print("OK")
else:
    print("NOT FOUND")
    # Bul
    import re
    for m in re.finditer(r'window\.shareInstagram', c):
        line = c[:m.start()].count('\n') + 1
        print(f"Satir {line}")
