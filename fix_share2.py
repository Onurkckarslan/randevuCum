c = open('app/templates/business/dashboard.html', encoding='utf-8').read()

old = """  const wpText = encodeURIComponent("Randevu linkim: " + bizUrl);

  window.shareWhatsApp = function() {
    window.open("https://wa.me/?text=" + wpText, "_blank");
  };

  window.shareFacebook = function() {
    window.open("https://www.facebook.com/sharer/sharer.php?u=" + encodeURIComponent(bizUrl), "_blank", "width=620,height=500");
  };

  window.shareInstagram = function() {
    copyText(bizUrl);
    window.open("instagram://", "_blank");
    setTimeout(function() {
      window.open("https://www.instagram.com/", "_blank");
    }, 1500);
    document.getElementById("igModal").classList.add("show");
  };"""

new = """  const wpText = encodeURIComponent("Randevu linkim: " + bizUrl);

  // Hepsinde Web Share API dene (mobilde native menü açar)
  // Desteklenmiyorsa platforma özgü fallback
  function doShare(fallback) {
    if (navigator.share) {
      navigator.share({
        title: "Randevu Linkim",
        text: "Online randevu icin: " + bizUrl,
        url: bizUrl,
      }).catch(function() { fallback(); });
    } else {
      fallback();
    }
  }

  window.shareWhatsApp = function() {
    doShare(function() {
      window.open("https://wa.me/?text=" + wpText, "_blank");
    });
  };

  window.shareFacebook = function() {
    doShare(function() {
      window.open("https://www.facebook.com/sharer/sharer.php?u=" + encodeURIComponent(bizUrl), "_blank", "width=620,height=500");
    });
  };

  window.shareInstagram = function() {
    doShare(function() {
      copyText(bizUrl);
      document.getElementById("igModal").classList.add("show");
    });
  };"""

if old in c:
    c = c.replace(old, new)
    open('app/templates/business/dashboard.html', 'w', encoding='utf-8').write(c)
    print("OK")
else:
    print("NOT FOUND")
