c = open('app/templates/business/dashboard.html', encoding='utf-8').read()

# shareWithQRAndLink bloğunun başı ve sonu
start = c.find('  function shareWithQRAndLink')
# closeIgModal'dan önce biten blok
end = c.find('  window.closeIgModal')

old_block = c[start:end]

new_block = """  const wpText = encodeURIComponent("Randevu linkim: " + bizUrl);

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
  };

"""

c = c[:start] + new_block + c[end:]
open('app/templates/business/dashboard.html', 'w', encoding='utf-8').write(c)
print("OK")
