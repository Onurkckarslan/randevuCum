c = open('app/templates/business/dashboard.html', encoding='utf-8').read()

old = """  window.shareInstagram = function() {
    // Linki kopyala
    copyText(bizUrl);
    // Instagram story kamerasını aç
    window.location.href = "instagram://camera";
    setTimeout(function() {
      // Uygulama açılmadıysa store'a yönlendir
      window.location.href = "https://www.instagram.com/";
    }, 2000);
    document.getElementById("igModal").classList.add("show");
  };"""

new = """  window.shareInstagram = function() {
    copyText(bizUrl);
    // Instagram uygulamasını aç (kullanıcı hikaye/chat seçer)
    window.location.href = "instagram://";
    setTimeout(function() {
      window.location.href = "https://www.instagram.com/";
    }, 2500);
    document.getElementById("igModal").classList.add("show");
  };"""

if old in c:
    c = c.replace(old, new)
    open('app/templates/business/dashboard.html', 'w', encoding='utf-8').write(c)
    print("OK")
else:
    print("NOT FOUND")
