c = open('app/templates/business/dashboard.html', encoding='utf-8').read()

start = c.find('  const wpText = encodeURIComponent')
end   = c.find('  window.closeIgModal')

new_block = """  window.shareWhatsApp = function() {
    var url = "https://wa.me/?text=" + encodeURIComponent("Randevu linkim: " + bizUrl);
    window.location.href = url;
  };

  window.shareFacebook = function() {
    var url = "fb://share?href=" + encodeURIComponent(bizUrl);
    window.location.href = url;
    setTimeout(function() {
      window.open("https://www.facebook.com/sharer/sharer.php?u=" + encodeURIComponent(bizUrl), "_blank");
    }, 1000);
  };

  window.shareInstagram = function() {
    copyText(bizUrl);
    document.getElementById("igModal").classList.add("show");
  };

"""

c = c[:start] + new_block + c[end:]
open('app/templates/business/dashboard.html', 'w', encoding='utf-8').write(c)
print("OK")
print("WhatsApp starts:", c.find('shareWhatsApp'))
