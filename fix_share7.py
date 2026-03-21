c = open('app/templates/business/dashboard.html', encoding='utf-8').read()

old = """  window.shareNative = function() {
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

new = """  window.shareNative = function() {
    if (navigator.share) {
      navigator.share({
        title: "Randevu Linkim",
        text: "Online randevu icin: " + bizUrl,
        url: bizUrl,
      }).catch(function() {
        copyText(bizUrl);
        showToast("Link kopyalandi!");
      });
    } else {
      copyText(bizUrl);
      showToast("Link kopyalandi!");
    }
  };

  function showToast(msg) {
    var t = document.createElement("div");
    t.textContent = msg;
    t.style.cssText = "position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#10b981;color:white;padding:10px 24px;border-radius:12px;font-weight:700;font-size:.9rem;z-index:9999;box-shadow:0 4px 20px rgba(0,0,0,.3);";
    document.body.appendChild(t);
    setTimeout(function() { t.remove(); }, 2500);
  }"""

if old in c:
    c = c.replace(old, new)
    open('app/templates/business/dashboard.html', 'w', encoding='utf-8').write(c)
    print("OK")
else:
    print("NOT FOUND")
