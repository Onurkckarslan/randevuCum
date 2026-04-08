from ..templates_config import templates
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, joinedload
from ..database import get_db
from ..models import Business, Service

router = APIRouter()

# ─── KATEGORİ VERİSİ ────────────────────────────────────────────────────────
KATEGORILER = {
    "kuaforler": {
        "slug": "kuaforler", "db": "kuafor", "isim": "Kuaförler", "emoji": "💇",
        "title": "Uşak Kuaförler — Randevu Al | RandevuCum",
        "aciklama": "Uşak'taki en iyi kuaförlerden online randevu alın. Saç kesimi, fön, boyama ve daha fazlası.",
        "ilgili": ["berberler", "guzellik", "tesettur"],
        "hizmetler": ["sac-kesimi", "fon", "sac-boyama", "gelin-basi", "rofle", "brezilya-fonu", "perma", "agda"],
        "icerik": {
            "h2": "Kuaförler Hakkında",
            "paragraflar": [
                "Saç bakım ve şekillendirilmesinde kadınlar için vazgeçilmez adreslerden biri olan kuaförler, profesyonel ekipleriyle her türlü saç hizmetini sunar.",
                "Kuaför seçiminde dikkat etmeniz gereken en önemli unsur hijyen ve profesyonelliktir. Uşak'taki kuaförlerimiz müşteri memnuniyetini ön planda tutar.",
                "Online randevu sistemi sayesinde telefonda bekleme yaşamadan istediğiniz saatte randevunuzu oluşturabilirsiniz.",
            ],
            "sss": [
                {"s": "Kuaförde saç kesimi ne kadar sürer?", "c": "Saç kesimi genellikle 30-60 dakika sürer."},
                {"s": "Online randevu nasıl alınır?", "c": "Listeden salonunuzu seçin, hizmet ve uygun saati belirleyin, adınızı ve telefonunuzu girin — randevunuz hazır!"},
                {"s": "Randevuyu iptal edebilir miyim?", "c": "Randevu öncesinde salonla iletişime geçerek iptal edebilirsiniz."},
            ],
        },
    },
    "berberler": {
        "slug": "berberler", "db": "berber", "isim": "Berberler", "emoji": "✂️",
        "title": "Uşak Berberler — Randevu Al | RandevuCum",
        "aciklama": "Uşak'taki berberlere online randevu alın. Saç kesimi, sakal tıraşı ve bakım hizmetleri.",
        "ilgili": ["kuaforler"],
        "hizmetler": ["sac-kesimi", "sakal-tirazi", "cocuk-tirazi"],
        "icerik": {
            "h2": "Berberler Hakkında",
            "paragraflar": [
                "Berberler, erkeklere yönelik saç kesimi, sakal tıraşı ve bakım hizmetleri sunan profesyonel salonlardır.",
                "Çocuk tıraşından damat tıraşına, klasik saç kesiminden modern stillere kadar geniş bir yelpazede hizmet sunan berberlerimizden online randevu alabilirsiniz.",
                "Bekleme kuyruğuna girmeden, telefon trafiği yaşamadan randevunuzu önceden ayarlayın.",
            ],
            "sss": [
                {"s": "Berberde saç kesimi ne kadar sürer?", "c": "Standart saç kesimi 20-40 dakika sürer."},
                {"s": "Sakal tıraşı için randevu gerekli mi?", "c": "Yoğun saatlerde beklememek için önceden randevu almanızı öneririz."},
            ],
        },
    },
    "guzellik": {
        "slug": "guzellik", "db": "guzellik", "isim": "Güzellik & Estetik Merkezleri", "emoji": "💅",
        "title": "Uşak Güzellik Merkezleri — Randevu Al | RandevuCum",
        "aciklama": "Uşak'taki güzellik ve estetik merkezlerine online randevu. Cilt bakımı, makyaj ve daha fazlası.",
        "ilgili": ["kuaforler", "tirnak", "spa"],
        "hizmetler": ["kas-alma", "makyaj", "ipek-kirpik", "cilt-bakimi", "agda"],
        "icerik": {
            "h2": "Güzellik & Estetik Merkezleri",
            "paragraflar": [
                "Güzellik ve estetik merkezleri cilt bakımı, makyaj, kaş şekillendirme, ipek kirpik ve daha pek çok hizmet sunar.",
                "Profesyonel ekipman ve deneyimli uzmanlarla kendinize özel bakım hizmetleri alın.",
            ],
            "sss": [
                {"s": "Cilt bakımı ne sıklıkla yapılmalı?", "c": "Uzmanlar ayda bir düzenli cilt bakımı yapılmasını önerir."},
                {"s": "Gelin makyajı için ne kadar önceden randevu almalıyım?", "c": "Özellikle yoğun sezonda en az 1-2 ay önceden randevu almanız önerilir."},
            ],
        },
    },
    "spa": {
        "slug": "spa", "db": "spa", "isim": "Spa & Masaj", "emoji": "🧖",
        "title": "Uşak Spa & Masaj — Randevu Al | RandevuCum",
        "aciklama": "Uşak'taki spa ve masaj merkezlerine online randevu. Masaj, sauna, hamam hizmetleri.",
        "ilgili": ["guzellik", "saglikli-yasam"],
        "hizmetler": ["masaj", "sauna", "hamam"],
        "icerik": {
            "h2": "Spa & Masaj Merkezleri",
            "paragraflar": [
                "Günlük stresin yorgunluğunu atmak için spa ve masaj merkezleri ideal dinlenme noktalarıdır.",
                "Kendinize zaman ayırın, uzman terapistlerin ellerinde dinlenin.",
            ],
            "sss": [
                {"s": "Masaj seansı ne kadar sürer?", "c": "Standart masaj seansları 30-90 dakika arasındadır."},
                {"s": "Spa'ya ne giymeli?", "c": "Spa merkezleri genellikle havlu ve terlik sağlar."},
            ],
        },
    },
    "solaryum": {
        "slug": "solaryum", "db": "solaryum", "isim": "Solaryum Merkezleri", "emoji": "☀️",
        "title": "Uşak Solaryum — Randevu Al | RandevuCum",
        "aciklama": "Uşak'taki solaryum merkezlerine online randevu alın.",
        "ilgili": ["spa", "guzellik"],
        "hizmetler": ["solaryum"],
        "icerik": {
            "h2": "Solaryum Merkezleri",
            "paragraflar": [
                "Solaryum merkezlerinde kontrollü UV ışığıyla bronz bir cilt tonuna kavuşabilirsiniz.",
                "Sağlıklı bronzlaşma için uzman tavsiyeleri alın.",
            ],
            "sss": [
                {"s": "Solaryum haftada kaç kez yapılmalı?", "c": "Uzmanlar haftada 2-3 seanstan fazla yapılmamasını önerir."},
                {"s": "İlk seans kaç dakika olmalı?", "c": "İlk seans için 5-8 dakika önerilir."},
            ],
        },
    },
    "tirnak": {
        "slug": "tirnak", "db": "tirnak", "isim": "Tırnak & Makyaj Stüdyoları", "emoji": "💎",
        "title": "Uşak Tırnak & Makyaj Stüdyoları — Randevu Al | RandevuCum",
        "aciklama": "Uşak'taki tırnak ve makyaj stüdyolarına online randevu. Jel tırnak, protez tırnak, makyaj.",
        "ilgili": ["guzellik", "kuaforler"],
        "hizmetler": ["jel-tirnak", "protez-tirnak", "kas-alma", "makyaj", "ipek-kirpik"],
        "icerik": {
            "h2": "Tırnak & Makyaj Stüdyoları",
            "paragraflar": [
                "Tırnak ve makyaj stüdyoları jel tırnak, protez tırnak, nail art, kalıcı oje ve profesyonel makyaj hizmetleri sunar.",
                "Özel günleriniz için gelin makyajı ve tırnak süsleme hizmetlerinden yararlanın.",
            ],
            "sss": [
                {"s": "Jel tırnak ne kadar dayanır?", "c": "Jel tırnak bakımı yapıldığında 3-4 hafta dayanır."},
                {"s": "Protez tırnak zararlı mı?", "c": "Doğru uygulama ve bakım yapıldığında protez tırnak zararsızdır."},
            ],
        },
    },
    "dovme": {
        "slug": "dovme", "db": "dovme", "isim": "Dövme & Piercing", "emoji": "🎨",
        "title": "Uşak Dövme & Piercing — Randevu Al | RandevuCum",
        "aciklama": "Uşak'taki dövme ve piercing stüdyolarına online randevu alın.",
        "ilgili": ["guzellik"],
        "hizmetler": ["kalici-dovme", "piercing"],
        "icerik": {
            "h2": "Dövme & Piercing Stüdyoları",
            "paragraflar": [
                "Profesyonel dövme ve piercing stüdyoları steril ortamda, deneyimli sanatçılarla hizmet verir.",
                "Hijyen ve güvenlik en önemli önceliğimizdir.",
            ],
            "sss": [
                {"s": "Dövme yaptırmadan önce ne yapmalıyım?", "c": "Tasarımınızı önceden belirlemeniz ve sanatçıyla detaylıca konuşmanız önerilir."},
                {"s": "Dövme iyileşmesi ne kadar sürer?", "c": "Yüzeysel iyileşme 2-3 hafta, tam iyileşme 3-6 ay sürebilir."},
            ],
        },
    },
    "saglikli-yasam": {
        "slug": "saglikli-yasam", "db": "saglikli-yasam", "isim": "Sağlıklı Yaşam Merkezleri", "emoji": "🏃",
        "title": "Uşak Sağlıklı Yaşam Merkezleri — Randevu Al | RandevuCum",
        "aciklama": "Uşak'taki pilates, yoga ve sağlıklı yaşam merkezlerine online randevu.",
        "ilgili": ["spa"],
        "hizmetler": ["pilates", "yoga"],
        "icerik": {
            "h2": "Sağlıklı Yaşam Merkezleri",
            "paragraflar": [
                "Pilates, yoga, fitness ve diğer sağlıklı yaşam aktiviteleri için Uşak'taki merkezlerden online randevu alabilirsiniz.",
                "Bireysel veya grup dersleri için uygun saatleri seçin.",
            ],
            "sss": [
                {"s": "Pilates başlamak için özel bir hazırlık gerekir mi?", "c": "Hayır, rahat kıyafetler yeterlidir."},
                {"s": "Yoga haftada kaç kez yapılmalı?", "c": "Haftada 2-3 seans ideal olarak kabul edilir."},
            ],
        },
    },
    "tesettur": {
        "slug": "tesettur", "db": "tesettur", "isim": "Tesettür Kuaförleri", "emoji": "🌸",
        "title": "Uşak Tesettür Kuaförleri — Randevu Al | RandevuCum",
        "aciklama": "Uşak'taki tesettür kuaförlerine online randevu alın. Kapalı, sadece kadınlara özel salonlar.",
        "ilgili": ["kuaforler", "guzellik"],
        "hizmetler": ["sac-kesimi", "fon", "sac-boyama", "gelin-basi", "agda"],
        "icerik": {
            "h2": "Tesettür Kuaförleri",
            "paragraflar": [
                "Tesettür kuaförleri sadece kadınlara özel, kapalı ortamda hizmet veren salonlardır.",
                "Mahremiyetinize özen gösterilen bu salonlarda güvenle hizmet alabilirsiniz.",
            ],
            "sss": [
                {"s": "Tesettür kuaförleri nedir?", "c": "Sadece kadın personelin çalıştığı ve kapalı ortamda hizmet veren kuaför salonlarıdır."},
                {"s": "Gelin saçı için ne zaman randevu almalıyım?", "c": "Düğün tarihinden en az 1-2 ay önce randevu almanız önerilir."},
            ],
        },
    },
    # ── YENİ KATEGORİLER ────────────────────────────────────────────────────
    "guzellik-estetik": {
        "slug": "guzellik-estetik", "db": "guzellik-estetik", "isim": "Güzellik & Estetik", "emoji": "💅",
        "title": "Güzellik & Estetik — Randevu Al | RandevuCum",
        "aciklama": "Profesyonel güzellik ve estetik uzmanlarından online randevu alın.",
        "ilgili": ["kuaforler", "tirnak", "spa"],
        "hizmetler": ["makyaj", "cilt-bakimi", "ipek-kirpik", "kas-alma", "agda"],
        "icerik": {
            "h2": "Güzellik & Estetik",
            "paragraflar": ["Cilt bakımı, makyaj, kaş tasarımı ve estetik uygulamalar için uzman salonlardan randevu alın."],
            "sss": [{"s": "Randevu nasıl alınır?", "c": "Listeden uzmanı seçin, uygun saati belirleyin ve randevunuzu oluşturun."}],
        },
    },
    "psikoloji": {
        "slug": "psikoloji", "db": "psikoloji", "isim": "Psikoloji & Danışmanlık", "emoji": "🧠",
        "title": "Psikoloji & Danışmanlık — Randevu Al | RandevuCum",
        "aciklama": "Uzman psikolog ve danışmanlardan online randevu alın. Bireysel, çift ve aile terapisi.",
        "ilgili": ["kocluk", "saglik"],
        "hizmetler": [],
        "icerik": {
            "h2": "Psikoloji & Danışmanlık",
            "paragraflar": ["Bireysel terapi, çift danışmanlığı ve aile terapisi için uzman psikologlardan randevu alın."],
            "sss": [{"s": "İlk seans nasıl geçer?", "c": "İlk seansta psikolog sizi tanımak ve ihtiyaçlarınızı anlamak için görüşme yapar."}],
        },
    },
    "beslenme-diyet": {
        "slug": "beslenme-diyet", "db": "beslenme-diyet", "isim": "Beslenme & Diyet", "emoji": "🥗",
        "title": "Beslenme & Diyet — Randevu Al | RandevuCum",
        "aciklama": "Uzman diyetisyen ve beslenme danışmanlarından kişiye özel diyet programı için randevu alın.",
        "ilgili": ["saglik", "spor-fitness"],
        "hizmetler": [],
        "icerik": {
            "h2": "Beslenme & Diyet",
            "paragraflar": ["Kilo kontrolü, sağlıklı beslenme ve özel diyet programları için uzman diyetisyenlerden randevu alın."],
            "sss": [{"s": "Diyetisyen seansı ne kadar sürer?", "c": "İlk seans genellikle 45-60 dakika sürer."}],
        },
    },
    "fizyoterapi": {
        "slug": "fizyoterapi", "db": "fizyoterapi", "isim": "Fizyoterapi & Terapi", "emoji": "🦴",
        "title": "Fizyoterapi & Terapi — Randevu Al | RandevuCum",
        "aciklama": "Uzman fizyoterapistlerden rehabilitasyon ve terapi için online randevu alın.",
        "ilgili": ["saglik", "spor-fitness"],
        "hizmetler": [],
        "icerik": {
            "h2": "Fizyoterapi & Terapi",
            "paragraflar": ["Spor yaralanmaları, bel-boyun ağrıları ve rehabilitasyon için uzman fizyoterapistlerden randevu alın."],
            "sss": [{"s": "Fizyoterapi seans süresi nedir?", "c": "Seans süresi 30-60 dakika arasında değişir."}],
        },
    },
    "dis-sagligi": {
        "slug": "dis-sagligi", "db": "dis-sagligi", "isim": "Ağız & Diş Sağlığı", "emoji": "🦷",
        "title": "Ağız & Diş Sağlığı — Randevu Al | RandevuCum",
        "aciklama": "Diş hekimi randevunuzu online alın. Dolgu, implant, ortodonti ve daha fazlası.",
        "ilgili": ["saglik"],
        "hizmetler": [],
        "icerik": {
            "h2": "Ağız & Diş Sağlığı",
            "paragraflar": ["Rutin diş kontrolü, dolgu, kanal tedavisi, implant ve ortodontik tedavi için online randevu alın."],
            "sss": [{"s": "Diş hekimine ne sıklıkla gidilmeli?", "c": "6 ayda bir düzenli kontrol önerilir."}],
        },
    },
    "spor-fitness": {
        "slug": "spor-fitness", "db": "spor-fitness", "isim": "Spor & Fitness", "emoji": "🏋️",
        "title": "Spor & Fitness — Randevu Al | RandevuCum",
        "aciklama": "Kişisel antrenörler ve fitness uzmanlarından randevu alın.",
        "ilgili": ["pilates-yoga", "fizyoterapi"],
        "hizmetler": ["pilates", "fitness"],
        "icerik": {
            "h2": "Spor & Fitness",
            "paragraflar": ["Kişisel antrenman, grup dersleri ve fitness danışmanlığı için uzman eğitmenlerden randevu alın."],
            "sss": [{"s": "Kişisel antrenman ne sıklıkla yapılmalı?", "c": "Hedeflerinize göre haftada 2-4 seans önerilir."}],
        },
    },
    "pilates-yoga": {
        "slug": "pilates-yoga", "db": "pilates-yoga", "isim": "Pilates & Yoga", "emoji": "🧘",
        "title": "Pilates & Yoga — Randevu Al | RandevuCum",
        "aciklama": "Pilates ve yoga stüdyolarından online randevu alın. Bireysel ve grup dersleri.",
        "ilgili": ["spor-fitness", "saglik"],
        "hizmetler": ["pilates", "yoga"],
        "icerik": {
            "h2": "Pilates & Yoga",
            "paragraflar": ["Vücut farkındalığı, esneklik ve zihinsel denge için pilates ve yoga derslerine katılın."],
            "sss": [{"s": "Başlangıç için hangi seviye?", "c": "Başlangıç seviyesinden başlayarak kademeli ilerleme önerilir."}],
        },
    },
    "egitim-ozel-ders": {
        "slug": "egitim-ozel-ders", "db": "egitim-ozel-ders", "isim": "Eğitim & Özel Ders", "emoji": "📚",
        "title": "Eğitim & Özel Ders — Randevu Al | RandevuCum",
        "aciklama": "Özel ders ve eğitim danışmanlarından online randevu alın.",
        "ilgili": ["kocluk"],
        "hizmetler": [],
        "icerik": {
            "h2": "Eğitim & Özel Ders",
            "paragraflar": ["Matematik, Türkçe, yabancı dil ve daha pek çok konuda uzman öğretmenlerden özel ders randevusu alın."],
            "sss": [{"s": "Özel ders süresi ne kadar?", "c": "Genellikle 45-90 dakika arasında değişir."}],
        },
    },
    "sanat-muzik": {
        "slug": "sanat-muzik", "db": "sanat-muzik", "isim": "Sanat & Müzik", "emoji": "🎸",
        "title": "Sanat & Müzik — Randevu Al | RandevuCum",
        "aciklama": "Sanat ve müzik eğitmenleri için online randevu alın.",
        "ilgili": ["egitim-ozel-ders"],
        "hizmetler": [],
        "icerik": {
            "h2": "Sanat & Müzik",
            "paragraflar": ["Resim, gitar, piyano, keman ve daha pek çok sanat dalında uzman eğitmenlerden ders alın."],
            "sss": [{"s": "Müzik dersine başlamak için yaş sınırı var mı?", "c": "Her yaştan kişi müzik dersine başlayabilir."}],
        },
    },
    "kocluk": {
        "slug": "kocluk", "db": "kocluk", "isim": "Koçluk & Kişisel Gelişim", "emoji": "🚀",
        "title": "Koçluk & Kişisel Gelişim — Randevu Al | RandevuCum",
        "aciklama": "Yaşam koçları ve kişisel gelişim uzmanlarından randevu alın.",
        "ilgili": ["psikoloji", "egitim-ozel-ders"],
        "hizmetler": [],
        "icerik": {
            "h2": "Koçluk & Kişisel Gelişim",
            "paragraflar": ["Kariyer, yaşam, iş ve liderlik koçluğu için uzman koçlardan randevu alın."],
            "sss": [{"s": "Koçluk ile psikoloji arasındaki fark?", "c": "Koçluk geleceğe odaklanır, psikoloji geçmiş ve mevcut durumu ele alır."}],
        },
    },
    "saglik": {
        "slug": "saglik", "db": "saglik", "isim": "Sağlık Merkezleri", "emoji": "🏥",
        "title": "Sağlık Merkezleri — Randevu Al | RandevuCum",
        "aciklama": "Sağlık merkezleri ve kliniklerden online randevu alın.",
        "ilgili": ["dis-sagligi", "fizyoterapi"],
        "hizmetler": [],
        "icerik": {
            "h2": "Sağlık Merkezleri",
            "paragraflar": ["Genel sağlık kontrolü, uzman muayene ve klinik hizmetler için online randevu alın."],
            "sss": [{"s": "Randevu almadan gidebilir miyim?", "c": "Bekleme süresini kısaltmak için önceden randevu almanız önerilir."}],
        },
    },
    "rehabilitasyon": {
        "slug": "rehabilitasyon", "db": "rehabilitasyon", "isim": "Rehabilitasyon & Özel Destek", "emoji": "💙",
        "title": "Rehabilitasyon & Özel Destek — Randevu Al | RandevuCum",
        "aciklama": "Rehabilitasyon ve özel destek merkezlerinden online randevu alın.",
        "ilgili": ["fizyoterapi", "saglik"],
        "hizmetler": [],
        "icerik": {
            "h2": "Rehabilitasyon & Özel Destek",
            "paragraflar": ["Fiziksel ve bilişsel rehabilitasyon, özel eğitim ve destek hizmetleri için uzman merkezlerden randevu alın."],
            "sss": [{"s": "Rehabilitasyon süreci ne kadar sürer?", "c": "Kişiye ve duruma göre değişir, uzmanınız size bilgi verecektir."}],
        },
    },
    "cocuk-aile": {
        "slug": "cocuk-aile", "db": "cocuk-aile", "isim": "Çocuk & Aile Hizmetleri", "emoji": "👨‍👩‍👧",
        "title": "Çocuk & Aile Hizmetleri — Randevu Al | RandevuCum",
        "aciklama": "Çocuk ve aile hizmetleri uzmanlarından online randevu alın.",
        "ilgili": ["psikoloji", "egitim-ozel-ders"],
        "hizmetler": [],
        "icerik": {
            "h2": "Çocuk & Aile Hizmetleri",
            "paragraflar": ["Çocuk psikolojisi, aile danışmanlığı, çocuk gelişimi ve özel eğitim hizmetleri için randevu alın."],
            "sss": [{"s": "Kaç yaşından itibaren çocuk psikologu gerekir?", "c": "Herhangi bir yaşta uzmana başvurulabilir, erken müdahale önemlidir."}],
        },
    },
    "kurumsal": {
        "slug": "kurumsal", "db": "kurumsal", "isim": "Kurumsal Danışmanlık", "emoji": "🏢",
        "title": "Kurumsal Danışmanlık — Randevu Al | RandevuCum",
        "aciklama": "İş ve kurumsal danışmanlık hizmetleri için online randevu alın.",
        "ilgili": ["kocluk"],
        "hizmetler": [],
        "icerik": {
            "h2": "Kurumsal Danışmanlık",
            "paragraflar": ["İnsan kaynakları, iş geliştirme, finans ve yönetim danışmanlığı için uzmanlardan randevu alın."],
            "sss": [{"s": "Kurumsal danışmanlık ne işe yarar?", "c": "İşletmenizin verimliliğini ve karlılığını artırmak için uzman desteği sağlar."}],
        },
    },
    "saglik-medikal": {
        "slug": "saglik-medikal", "db": "saglik-medikal", "isim": "Sağlık & Medikal", "emoji": "⚕️",
        "title": "Sağlık & Medikal — Randevu Al | RandevuCum",
        "aciklama": "Medikal klinikler ve sağlık uzmanlarından online randevu alın.",
        "ilgili": ["saglik", "fizyoterapi"],
        "hizmetler": [],
        "icerik": {
            "h2": "Sağlık & Medikal",
            "paragraflar": ["Estetik medikal uygulamalar, genel sağlık hizmetleri ve medikal kliniklerden online randevu alın."],
            "sss": [{"s": "Medikal işlemler için randevu şart mı?", "c": "Evet, bekleme süresini kısaltmak ve doğru hazırlık için randevu almanız önerilir."}],
        },
    },
    "rent-a-car": {
        "slug": "rent-a-car", "db": "rent-a-car", "isim": "Rent A Car", "emoji": "🚗",
        "title": "Araç Kiralama Hizmetleri — Randevu Al | RandevuCum",
        "aciklama": "Uşak'taki araç kiralama şirketlerinden online rezervasyon yapın. Uygun fiyatlar ve kaliteli araçlar.",
        "ilgili": [],
        "hizmetler": [],
        "icerik": {
            "h2": "Rent A Car - Araç Kiralama",
            "paragraflar": [
                "Uygun fiyatlarla kaliteli araçlar kiralayın. Profesyonel hizmet ve güvenilir şirketlerden seçim yapın.",
                "Online rezervasyon yaparak aradığınız araçları kolayca bulun ve kiralayın.",
            ],
            "sss": [
                {"s": "Araç kiralama için minimum yaş gerekli midir?", "c": "Evet, çoğu şirket en az 25 yaş şartı koşmaktadır."},
                {"s": "Kaç gün önceden rezervasyon yapabilirim?", "c": "Genellikle bir yıl öncesinden rezervasyon yapabilirsiniz."},
            ],
        },
        "is_rental": True,
    },
    "oto-yikama": {
        "slug": "oto-yikama", "db": "oto-yikama", "isim": "Oto Yıkama", "emoji": "🚿",
        "title": "Uşak Oto Yıkama — Randevu Al | RandevuCum",
        "aciklama": "Uşak'taki oto yıkama merkezlerinden online randevu alın. Dış yıkama, iç temizlik ve balmumu.",
        "ilgili": ["otopark"],
        "hizmetler": ["dis-yikama", "ic-temizlik", "motor-temizlik"],
        "icerik": {
            "h2": "Oto Yıkama Merkezleri",
            "paragraflar": [
                "Aracınızın bakımı ve temizliği için profesyonel oto yıkama merkezleri en güvenilir seçeneklerdir.",
                "Dış yıkamadan iç temizliğine, motor yıkamalarından özel balmumu uygulamalarına kadar geniş bir hizmet yelpazesi.",
                "Online randevu sistemi ile sıraya girmeden aracınızın bakımını yaptırın.",
            ],
            "sss": [
                {"s": "Oto yıkama ne sıklıkla yapılmalı?", "c": "Haftada bir veya 15 günde bir oto yıkama önerilir."},
                {"s": "Balmumu ne işe yarar?", "c": "Balmumu, araç boyasını korur ve yağmurdan kaynaklanan hasarları azaltır."},
            ],
        },
    },
    "otopark": {
        "slug": "otopark", "db": "otopark", "isim": "Otopark", "emoji": "🅿️",
        "title": "Uşak Otopark — Randevu Al | RandevuCum",
        "aciklama": "Uşak'taki otopark alanlarına online rezervasyon yapın. Güvenli ve uygun fiyatlı otopark hizmetleri.",
        "ilgili": ["oto-yikama"],
        "hizmetler": ["saatlik-otopark", "gunluk-otopark"],
        "icerik": {
            "h2": "Otopark Hizmetleri",
            "paragraflar": [
                "Şehir merkezinde güvenli ve rahat otopark alanları bulunması her zaman sorun olmuştur.",
                "Online otopark rezervasyon sistemi ile aracınızın park ettiği yeri önceden belirleyin, saat başında ücret ödeyin.",
            ],
            "sss": [
                {"s": "Otopark ücretleri nasıl hesaplanır?", "c": "Çoğu otopark saatlik tarife üzerinden ücretlendirilir."},
                {"s": "Gece parkı daha mı ucuzdur?", "c": "Evet, gece parkı genellikle daha avantajlı fiyatlara sunulur."},
            ],
        },
    },
    "otel-pansiyon": {
        "slug": "otel-pansiyon", "db": "otel-pansiyon", "isim": "Otel & Pansiyon", "emoji": "🏨",
        "title": "Uşak Otelleri — Konaklama Yeri Bul | RandevuCum",
        "aciklama": "Uşak'taki oteller ve pansiyonlara online rezervasyon yapın. Konforlu konaklama, uygun fiyatlar.",
        "ilgili": [],
        "hizmetler": ["standart-oda", "suite-oda", "deluxe-oda"],
        "icerik": {
            "h2": "Otel & Pansiyon Hizmetleri",
            "paragraflar": [
                "Uşak'ta rahat ve güvenli bir şekilde konaklamak için birçok otel ve pansiyon seçeneği mevcuttur.",
                "Her bütçeye uygun oda tipleri ve hizmetler sunan oteller ve pansiyonlardan seçim yapın.",
                "Online rezervasyon sistemi ile istediğiniz tarihlerde en uygun fiyatlı odayı ayırtın.",
            ],
            "sss": [
                {"s": "Check-in saati kaçta?", "c": "Genellikle öğleden sonra 14:00-15:00'te check-in yapılır."},
                {"s": "İptal politikası nedir?", "c": "Çoğu otel konaklama tarihinden 24 saat öncesine kadar ücretsiz iptal imkanı sunar."},
            ],
        },
        "is_daily": True,
    },
}

# ─── HİZMET VERİSİ ──────────────────────────────────────────────────────────
HIZMETLER = {
    "sac-kesimi": {
        "isim": "Saç Kesimi", "emoji": "✂️",
        "title": "Uşak Saç Kesimi — Randevu Al | RandevuCum",
        "aciklama": "Uşak'ta saç kesimi yaptırmak için online randevu alın.",
        "kategori_db": ["kuafor", "berber", "tesettur"],
        "ilgili_hizmetler": ["fon", "sac-boyama", "brezilya-fonu"],
        "icerik": {
            "h2": "Saç Kesimi Hakkında",
            "paragraflar": [
                "Saç kesimi, saç sağlığı ve görünümü için en temel bakım adımlarından biridir.",
                "Saç kesimi süresi ve ücreti; saçın uzunluğuna, kalınlığına ve istenilen modele göre değişir.",
                "Saçınızı en son trendlere göre şekillendirmek için salon sayfasını inceleyip uygun saatte randevunuzu oluşturun.",
            ],
            "sss": [
                {"s": "Saç kesimi ne sıklıkla yapılmalı?", "c": "Uzmanlar 6-8 haftada bir saç kesimi yaptırılmasını önerir."},
                {"s": "Saç kesiminde ne kadar ücret ödenir?", "c": "Saç kesimi ücretleri salona ve modele göre değişir."},
                {"s": "Hangi saç modelini seçmeliyim?", "c": "Yüz şeklinize uygun modeller için kuaförünüzle danışabilirsiniz."},
            ],
        },
    },
    "fon": {
        "isim": "Fön", "emoji": "💨",
        "title": "Uşak Fön — Randevu Al | RandevuCum",
        "aciklama": "Uşak'ta fön çektirmek için online randevu alın.",
        "kategori_db": ["kuafor", "tesettur"],
        "ilgili_hizmetler": ["sac-kesimi", "brezilya-fonu", "sac-boyama"],
        "icerik": {
            "h2": "Fön Hakkında",
            "paragraflar": [
                "Fön, saçın şekillendirilmesi ve hacim kazandırılması için en çok tercih edilen saç bakım hizmetlerinden biridir.",
                "Özel günler, davetler veya günlük bakım için fön randevusu alabilirsiniz.",
            ],
            "sss": [
                {"s": "Fön ne kadar sürer?", "c": "Saç uzunluğuna göre 30-60 dakika sürer."},
                {"s": "Brezilya fönü ile normal fön arasındaki fark nedir?", "c": "Brezilya fönü 2-3 ay kalıcı düzlük sağlar, normal fön ise birkaç gün etkili olur."},
            ],
        },
    },
    "sac-boyama": {
        "isim": "Saç Boyama", "emoji": "🎨",
        "title": "Uşak Saç Boyama — Randevu Al | RandevuCum",
        "aciklama": "Uşak'ta saç boyama için online randevu alın.",
        "kategori_db": ["kuafor", "tesettur"],
        "ilgili_hizmetler": ["rofle", "sac-kesimi", "brezilya-fonu"],
        "icerik": {
            "h2": "Saç Boyama Hakkında",
            "paragraflar": [
                "Saç boyama; tek renk boyama, röfle, ombre, sombre ve balayage gibi pek çok teknikle uygulanabilir.",
                "Kaliteli boyalar kullanılarak yapılan saç boyama işlemi saç sağlığını korur.",
            ],
            "sss": [
                {"s": "Saç boyama ne kadar sürer?", "c": "Tek renk boyama 1-2 saat, röfle veya ombre 2-4 saat sürebilir."},
                {"s": "Saç boyama sıklığı ne olmalı?", "c": "Diplerin belli olmasına göre genellikle 4-6 haftada bir yapılır."},
            ],
        },
    },
    "gelin-basi": {
        "isim": "Gelin Başı", "emoji": "👰",
        "title": "Uşak Gelin Başı — Randevu Al | RandevuCum",
        "aciklama": "Uşak'ta gelin saçı ve gelin başı için online randevu alın.",
        "kategori_db": ["kuafor", "tesettur"],
        "ilgili_hizmetler": ["makyaj", "fon", "sac-boyama"],
        "icerik": {
            "h2": "Gelin Başı Hakkında",
            "paragraflar": [
                "Düğün gününüzün en özel anlarından biri olan gelin saçı, deneyimli kuaförler tarafından özenle hazırlanır.",
                "Uşak'taki gelin saçı uzmanı kuaförlerimizle önceden prova seansı yapabilirsiniz.",
            ],
            "sss": [
                {"s": "Gelin saçı için ne zaman randevu almalıyım?", "c": "En az 2-3 ay önceden randevu almanız önerilir."},
                {"s": "Prova seansı gerekli mi?", "c": "Evet, düğün öncesi prova seansı yapmanız son derece önerilir."},
            ],
        },
    },
    "rofle": {
        "isim": "Röfle & Gölge", "emoji": "🌟",
        "title": "Uşak Röfle — Randevu Al | RandevuCum",
        "aciklama": "Uşak'ta röfle ve gölge boyama için online randevu alın.",
        "kategori_db": ["kuafor", "tesettur"],
        "ilgili_hizmetler": ["sac-boyama", "fon"],
        "icerik": {
            "h2": "Röfle & Gölge Boyama",
            "paragraflar": [
                "Röfle, saça boyama teknikleriyle ışıltı ve derinlik katan bir uygulamadır.",
                "Uşak'taki kuaförlerimizde deneyimli boyama uzmanları en güncel tekniklerle röfle uygulaması yapmaktadır.",
            ],
            "sss": [
                {"s": "Röfle ne kadar sürer?", "c": "Röfle uygulaması saçın uzunluğuna göre 2-4 saat sürer."},
                {"s": "Röfle ne sıklıkla yenilenmeli?", "c": "Genellikle 2-3 ayda bir yenilenmesi önerilir."},
            ],
        },
    },
    "brezilya-fonu": {
        "isim": "Brezilya Fönü", "emoji": "💆",
        "title": "Uşak Brezilya Fönü — Randevu Al | RandevuCum",
        "aciklama": "Uşak'ta brezilya fönü için online randevu alın.",
        "kategori_db": ["kuafor", "tesettur"],
        "ilgili_hizmetler": ["fon", "sac-kesimi"],
        "icerik": {
            "h2": "Brezilya Fönü Hakkında",
            "paragraflar": [
                "Brezilya fönü (keratin bakımı), kıvırcık ve dalgalı saçları 2-3 ay boyunca düz ve parlak tutan bir saç bakım uygulamasıdır.",
                "Uşak'taki kuaförlerimizde kaliteli keratin ürünleriyle uygulanan brezilya fönü saçınıza canlılık ve bakım katar.",
            ],
            "sss": [
                {"s": "Brezilya fönü ne kadar sürer?", "c": "Uygulama 3-5 saat sürer. İşlemden sonra 3 gün saç yıkanmamalıdır."},
                {"s": "Her saça uygulanabilir mi?", "c": "Kıvırcık, dalgalı ve frizli saçlarda çok iyi sonuç verir."},
            ],
        },
    },
    "perma": {
        "isim": "Perma", "emoji": "🌀",
        "title": "Uşak Perma — Randevu Al | RandevuCum",
        "aciklama": "Uşak'ta perma için online randevu alın.",
        "kategori_db": ["kuafor", "tesettur"],
        "ilgili_hizmetler": ["sac-boyama", "fon"],
        "icerik": {
            "h2": "Perma Hakkında",
            "paragraflar": ["Perma (kalıcı ondülasyon), düz saçlara kalıcı dalga veya kıvrım kazandıran bir saç işlemidir."],
            "sss": [{"s": "Perma ne kadar kalıcıdır?", "c": "Ortalama 3-6 ay kalıcıdır."}],
        },
    },
    "sakal-tirazi": {
        "isim": "Sakal Tıraşı", "emoji": "🪒",
        "title": "Uşak Sakal Tıraşı — Randevu Al | RandevuCum",
        "aciklama": "Uşak'taki berberlere sakal tıraşı için online randevu alın.",
        "kategori_db": ["berber"],
        "ilgili_hizmetler": ["sac-kesimi", "cocuk-tirazi"],
        "icerik": {
            "h2": "Sakal Tıraşı Hakkında",
            "paragraflar": ["Sakal tıraşı ve şekillendirme, erkek bakımının ayrılmaz bir parçasıdır."],
            "sss": [{"s": "Sakal bakımı ne sıklıkla yapılmalı?", "c": "Sakalın uzunluğuna ve şekline göre 1-2 haftada bir önerilir."}],
        },
    },
    "cocuk-tirazi": {
        "isim": "Çocuk Tıraşı", "emoji": "👦",
        "title": "Uşak Çocuk Tıraşı — Randevu Al | RandevuCum",
        "aciklama": "Uşak'taki berber ve kuaförlere çocuk tıraşı için online randevu alın.",
        "kategori_db": ["berber", "kuafor"],
        "ilgili_hizmetler": ["sac-kesimi"],
        "icerik": {
            "h2": "Çocuk Tıraşı Hakkında",
            "paragraflar": ["Çocuklara özel yaklaşımıyla hizmet veren berber ve kuaförlerimiz, minik müşterilerin tıraşını keyifli bir deneyime dönüştürür."],
            "sss": [{"s": "Kaç yaşından itibaren kuaföre götürebilirim?", "c": "Bebekler dahil her yaşta kuaföre götürebilirsiniz."}],
        },
    },
    "kas-alma": {
        "isim": "Kaş Alma", "emoji": "👁️",
        "title": "Uşak Kaş Alma — Randevu Al | RandevuCum",
        "aciklama": "Uşak'ta kaş alma ve kaş şekillendirme için online randevu alın.",
        "kategori_db": ["kuafor", "guzellik", "tirnak"],
        "ilgili_hizmetler": ["makyaj", "ipek-kirpik"],
        "icerik": {
            "h2": "Kaş Alma & Şekillendirme",
            "paragraflar": ["Kaş şekillendirme, yüz ifadesini çerçeveleyen en önemli güzellik uygulamalarından biridir."],
            "sss": [{"s": "Kaş alma ne sıklıkla yapılmalı?", "c": "Genellikle 2-4 haftada bir yaptırılması önerilir."}],
        },
    },
    "makyaj": {
        "isim": "Makyaj", "emoji": "💄",
        "title": "Uşak Makyaj — Randevu Al | RandevuCum",
        "aciklama": "Uşak'ta profesyonel makyaj için online randevu alın.",
        "kategori_db": ["guzellik", "tirnak"],
        "ilgili_hizmetler": ["gelin-basi", "kas-alma", "ipek-kirpik"],
        "icerik": {
            "h2": "Profesyonel Makyaj",
            "paragraflar": ["Günlük, gece, gelin ve özel etkinlik makyajı için Uşak'taki profesyonel makyaj sanatçılarından randevu alabilirsiniz."],
            "sss": [{"s": "Gelin makyajı ne kadar sürer?", "c": "Gelin makyajı genellikle 1-2 saat sürer."}],
        },
    },
    "ipek-kirpik": {
        "isim": "İpek Kirpik", "emoji": "✨",
        "title": "Uşak İpek Kirpik — Randevu Al | RandevuCum",
        "aciklama": "Uşak'ta ipek kirpik uygulaması için online randevu alın.",
        "kategori_db": ["guzellik", "tirnak"],
        "ilgili_hizmetler": ["kas-alma", "makyaj"],
        "icerik": {
            "h2": "İpek Kirpik Hakkında",
            "paragraflar": ["İpek kirpik uygulaması, doğal kirpiklerinize tek tek yapıştırılan sentetik veya doğal kirpiklerle hacim ve uzunluk kazandırma işlemidir."],
            "sss": [
                {"s": "İpek kirpik ne kadar dayanır?", "c": "Bakımla birlikte 3-4 hafta dayanır."},
                {"s": "İpek kirpik zararlı mı?", "c": "Profesyonel eller tarafından uygulandığında güvenlidir."},
            ],
        },
    },
    "jel-tirnak": {
        "isim": "Jel Tırnak", "emoji": "💅",
        "title": "Uşak Jel Tırnak — Randevu Al | RandevuCum",
        "aciklama": "Uşak'ta jel tırnak uygulaması için online randevu alın.",
        "kategori_db": ["tirnak"],
        "ilgili_hizmetler": ["protez-tirnak", "makyaj"],
        "icerik": {
            "h2": "Jel Tırnak Hakkında",
            "paragraflar": ["Jel tırnak, doğal tırnak üzerine uygulanan ve UV ışığıyla sertleşen esnek bir tırnak kaplama yöntemidir."],
            "sss": [{"s": "Jel tırnak ne kadar dayanır?", "c": "Bakımla 3-4 hafta dayanır."}],
        },
    },
    "protez-tirnak": {
        "isim": "Protez Tırnak", "emoji": "💅",
        "title": "Uşak Protez Tırnak — Randevu Al | RandevuCum",
        "aciklama": "Uşak'ta protez tırnak uygulaması için online randevu alın.",
        "kategori_db": ["tirnak"],
        "ilgili_hizmetler": ["jel-tirnak"],
        "icerik": {
            "h2": "Protez Tırnak Hakkında",
            "paragraflar": ["Protez tırnak, kısa veya kırık tırnakları uzatmak ve şekillendirmek için kullanılan bir uygulamadır."],
            "sss": [{"s": "Protez tırnak ne kadar dayanır?", "c": "Bakım yapıldığında 3-4 hafta dayanır."}],
        },
    },
    "masaj": {
        "isim": "Masaj", "emoji": "🤲",
        "title": "Uşak Masaj — Randevu Al | RandevuCum",
        "aciklama": "Uşak'taki masaj merkezlerine online randevu alın.",
        "kategori_db": ["spa"],
        "ilgili_hizmetler": ["sauna", "hamam"],
        "icerik": {
            "h2": "Masaj Hakkında",
            "paragraflar": ["Klasik masajdan aromaterapi masajına, spor masajından derin doku masajına kadar pek çok çeşit masaj hizmeti mevcuttur."],
            "sss": [{"s": "Masaj ne kadar sürer?", "c": "Standart bir masaj seansı 30-90 dakika sürer."}],
        },
    },
    "sauna": {
        "isim": "Sauna", "emoji": "🧖",
        "title": "Uşak Sauna — Randevu Al | RandevuCum",
        "aciklama": "Uşak'taki sauna ve ıslak alan hizmetlerine online randevu alın.",
        "kategori_db": ["spa"],
        "ilgili_hizmetler": ["hamam", "masaj"],
        "icerik": {
            "h2": "Sauna Hakkında",
            "paragraflar": ["Sauna, vücudu detoks yapmanın ve stresi atmanın en etkili yollarından biridir."],
            "sss": [{"s": "Sauna ne sıklıkla kullanılmalı?", "c": "Haftada 1-2 kez ideal kabul edilir."}],
        },
    },
    "hamam": {
        "isim": "Hamam", "emoji": "🛁",
        "title": "Uşak Hamam — Randevu Al | RandevuCum",
        "aciklama": "Uşak'taki hamam ve kese-köpük hizmetlerine online randevu alın.",
        "kategori_db": ["spa"],
        "ilgili_hizmetler": ["sauna", "masaj"],
        "icerik": {
            "h2": "Hamam Hakkında",
            "paragraflar": ["Geleneksel Türk hamamı deneyimi için Uşak'taki hamam merkezlerimizden randevu alabilirsiniz."],
            "sss": [{"s": "Hamama ne sıklıkla gidilmeli?", "c": "Ayda 1-2 kez gitmek cilt sağlığı açısından idealdir."}],
        },
    },
    "solaryum": {
        "isim": "Solaryum", "emoji": "☀️",
        "title": "Uşak Solaryum — Randevu Al | RandevuCum",
        "aciklama": "Uşak'taki solaryum merkezlerine online randevu alın.",
        "kategori_db": ["solaryum"],
        "ilgili_hizmetler": ["masaj"],
        "icerik": {
            "h2": "Solaryum Hakkında",
            "paragraflar": ["Solaryum, kontrollü UV ışığıyla bronz bir cilt tonuna kavuşmanızı sağlar."],
            "sss": [{"s": "Solaryum fiyatı ne kadar?", "c": "Dakika bazlı ücretlendirme yapılır."}],
        },
    },
    "agda": {
        "isim": "Ağda", "emoji": "🪵",
        "title": "Uşak Ağda — Randevu Al | RandevuCum",
        "aciklama": "Uşak'ta ağda için online randevu alın.",
        "kategori_db": ["kuafor", "guzellik", "tesettur"],
        "ilgili_hizmetler": ["kas-alma", "makyaj"],
        "icerik": {
            "h2": "Ağda Hakkında",
            "paragraflar": ["Ağda, vücut tüy temizliğinde en çok tercih edilen yöntemlerden biridir."],
            "sss": [{"s": "Ağda ne sıklıkla yapılmalı?", "c": "Genellikle 3-4 haftada bir yaptırılması önerilir."}],
        },
    },
    "pilates": {
        "isim": "Pilates", "emoji": "🤸",
        "title": "Uşak Pilates — Randevu Al | RandevuCum",
        "aciklama": "Uşak'taki pilates stüdyolarına online randevu alın.",
        "kategori_db": ["saglikli-yasam"],
        "ilgili_hizmetler": ["yoga"],
        "icerik": {
            "h2": "Pilates Hakkında",
            "paragraflar": ["Pilates, vücut farkındalığı ve çekirdek kas gücünü geliştiren bir egzersiz yöntemidir."],
            "sss": [{"s": "Pilates başlamak için yaş sınırı var mı?", "c": "Her yaştan kişi pilates yapabilir."}],
        },
    },
    "yoga": {
        "isim": "Yoga", "emoji": "🧘",
        "title": "Uşak Yoga — Randevu Al | RandevuCum",
        "aciklama": "Uşak'taki yoga merkezlerine online randevu alın.",
        "kategori_db": ["saglikli-yasam"],
        "ilgili_hizmetler": ["pilates", "masaj"],
        "icerik": {
            "h2": "Yoga Hakkında",
            "paragraflar": ["Yoga, beden ve zihin sağlığını bir arada geliştiren kadim bir pratiktir."],
            "sss": [{"s": "Yogaya başlamak için ne gerekli?", "c": "Yoga matı ve rahat kıyafet yeterlidir."}],
        },
    },
    "kalici-dovme": {
        "isim": "Kalıcı Dövme", "emoji": "🎨",
        "title": "Uşak Kalıcı Dövme — Randevu Al | RandevuCum",
        "aciklama": "Uşak'taki dövme stüdyolarına online randevu alın.",
        "kategori_db": ["dovme"],
        "ilgili_hizmetler": ["piercing"],
        "icerik": {
            "h2": "Kalıcı Dövme Hakkında",
            "paragraflar": ["Kalıcı dövme, cilt altına pigment enjekte edilerek oluşturulan kalıcı bir sanat eseridir."],
            "sss": [{"s": "Dövme iyileşmesi ne kadar sürer?", "c": "Yüzeysel iyileşme 2-3 hafta, tam iyileşme 3-6 ay sürer."}],
        },
    },
    "piercing": {
        "isim": "Piercing", "emoji": "💍",
        "title": "Uşak Piercing — Randevu Al | RandevuCum",
        "aciklama": "Uşak'taki piercing stüdyolarına online randevu alın.",
        "kategori_db": ["dovme"],
        "ilgili_hizmetler": ["kalici-dovme"],
        "icerik": {
            "h2": "Piercing Hakkında",
            "paragraflar": ["Profesyonel piercing uygulaması için steril ortam ve deneyimli uzman şarttır."],
            "sss": [{"s": "Piercing iyileşmesi ne kadar sürer?", "c": "Kulak piercingi 6-8 hafta, diğer bölgeler daha uzun sürebilir."}],
        },
    },
    "cilt-bakimi": {
        "isim": "Cilt Bakımı", "emoji": "🌿",
        "title": "Uşak Cilt Bakımı — Randevu Al | RandevuCum",
        "aciklama": "Uşak'taki güzellik merkezlerine cilt bakımı için online randevu alın.",
        "kategori_db": ["guzellik"],
        "ilgili_hizmetler": ["makyaj", "kas-alma"],
        "icerik": {
            "h2": "Cilt Bakımı Hakkında",
            "paragraflar": ["Profesyonel cilt bakımı, cildinizin ihtiyaçlarına göre özel olarak hazırlanır."],
            "sss": [{"s": "Cilt bakımı ne sıklıkla yapılmalı?", "c": "Ayda bir profesyonel cilt bakımı yaptırmanız önerilir."}],
        },
    },
    "fitness": {
        "isim": "Fitness", "emoji": "🏋️",
        "title": "Uşak Fitness — Randevu Al | RandevuCum",
        "aciklama": "Uşak'taki fitness ve spor salonlarına online randevu alın.",
        "kategori_db": ["spor-fitness", "saglikli-yasam"],
        "ilgili_hizmetler": ["pilates", "yoga"],
        "icerik": {
            "h2": "Fitness Hakkında",
            "paragraflar": ["Kişisel antrenman ve fitness danışmanlığı için uzman eğitmenlerden randevu alın."],
            "sss": [{"s": "Fitness salonuna başlamak için ne gerekli?", "c": "Rahat spor kıyafeti ve motivasyon yeterlidir."}],
        },
    },
    "sac-bakimi": {
        "isim": "Saç Bakımı", "emoji": "💆",
        "title": "Uşak Saç Bakımı — Randevu Al | RandevuCum",
        "aciklama": "Uşak'ta profesyonel saç bakımı için online randevu alın.",
        "kategori_db": ["kuafor", "tesettur"],
        "ilgili_hizmetler": ["sac-kesimi", "brezilya-fonu", "fon"],
        "icerik": {
            "h2": "Saç Bakımı Hakkında",
            "paragraflar": ["Saç bakımı, saçın sağlığını ve güzelliğini korumanın en temel yoludur."],
            "sss": [{"s": "Saç bakımı ne sıklıkla yapılmalı?", "c": "Ayda bir profesyonel bakım yaptırmanız önerilir."}],
        },
    },
}

# ─── ROUTES ─────────────────────────────────────────────────────────────────

@router.get("/kategori/{slug}", response_class=HTMLResponse)
async def category_page(slug: str, request: Request, db: Session = Depends(get_db)):
    kat = KATEGORILER.get(slug)
    if not kat:
        raise HTTPException(status_code=404)
    businesses = db.query(Business).options(
        joinedload(Business.photos),
        joinedload(Business.services),
        joinedload(Business.work_hours),
    ).filter(Business.category == kat["db"], Business.is_active == True).all()
    return templates.TemplateResponse("category.html", {
        "request": request, "kat": kat, "businesses": businesses,
        "tum_kategoriler": KATEGORILER, "hizmet_map": HIZMETLER,
    })


@router.get("/hizmet/{slug}", response_class=HTMLResponse)
async def service_page(slug: str, request: Request, db: Session = Depends(get_db)):
    hizmet = HIZMETLER.get(slug)
    if not hizmet:
        raise HTTPException(status_code=404)
    businesses = db.query(Business).join(Service, Service.business_id == Business.id).filter(
        Service.name.ilike(f"%{hizmet['isim']}%"), Business.is_active == True
    ).distinct().all()
    if not businesses:
        businesses = db.query(Business).filter(
            Business.category.in_(hizmet["kategori_db"]), Business.is_active == True
        ).all()
    return templates.TemplateResponse("service_page.html", {
        "request": request, "hizmet": hizmet, "hizmet_slug": slug,
        "businesses": businesses, "tum_hizmetler": HIZMETLER, "hizmet_map": HIZMETLER,
    })


# ── KATEGORİ KISA URL'LERİ ───────────────────────────────────────────────────
@router.get("/kuaforler", response_class=HTMLResponse)
async def r_kuaforler(request: Request, db: Session = Depends(get_db)):
    return await category_page("kuaforler", request, db)

@router.get("/berberler", response_class=HTMLResponse)
async def r_berberler(request: Request, db: Session = Depends(get_db)):
    return await category_page("berberler", request, db)

@router.get("/guzellik-merkezleri", response_class=HTMLResponse)
async def r_guzellik(request: Request, db: Session = Depends(get_db)):
    return await category_page("guzellik", request, db)

@router.get("/spalar", response_class=HTMLResponse)
async def r_spa(request: Request, db: Session = Depends(get_db)):
    return await category_page("spa", request, db)

@router.get("/solaryum-merkezleri", response_class=HTMLResponse)
async def r_solaryum(request: Request, db: Session = Depends(get_db)):
    return await category_page("solaryum", request, db)

@router.get("/tirnak-makyaj", response_class=HTMLResponse)
async def r_tirnak(request: Request, db: Session = Depends(get_db)):
    return await category_page("tirnak", request, db)

@router.get("/dovme-tattoo", response_class=HTMLResponse)
async def r_dovme(request: Request, db: Session = Depends(get_db)):
    return await category_page("dovme", request, db)

@router.get("/saglikli-yasam", response_class=HTMLResponse)
async def r_saglikli(request: Request, db: Session = Depends(get_db)):
    return await category_page("saglikli-yasam", request, db)

@router.get("/tesettur-kuaforleri", response_class=HTMLResponse)
async def r_tesettur(request: Request, db: Session = Depends(get_db)):
    return await category_page("tesettur", request, db)

# ── YENİ KATEGORİ KISA URL'LERİ ─────────────────────────────────────────────
@router.get("/guzellik-estetik", response_class=HTMLResponse)
async def r_guzellik_estetik(request: Request, db: Session = Depends(get_db)):
    return await category_page("guzellik-estetik", request, db)

@router.get("/psikoloji-danismanlik", response_class=HTMLResponse)
async def r_psikoloji(request: Request, db: Session = Depends(get_db)):
    return await category_page("psikoloji", request, db)

@router.get("/beslenme-diyet", response_class=HTMLResponse)
async def r_beslenme(request: Request, db: Session = Depends(get_db)):
    return await category_page("beslenme-diyet", request, db)

@router.get("/fizyoterapi", response_class=HTMLResponse)
async def r_fizyoterapi(request: Request, db: Session = Depends(get_db)):
    return await category_page("fizyoterapi", request, db)

@router.get("/dis-sagligi", response_class=HTMLResponse)
async def r_dis(request: Request, db: Session = Depends(get_db)):
    return await category_page("dis-sagligi", request, db)

@router.get("/spor-fitness", response_class=HTMLResponse)
async def r_spor(request: Request, db: Session = Depends(get_db)):
    return await category_page("spor-fitness", request, db)

@router.get("/pilates-yoga", response_class=HTMLResponse)
async def r_pilates_yoga(request: Request, db: Session = Depends(get_db)):
    return await category_page("pilates-yoga", request, db)

@router.get("/egitim-ozel-ders", response_class=HTMLResponse)
async def r_egitim(request: Request, db: Session = Depends(get_db)):
    return await category_page("egitim-ozel-ders", request, db)

@router.get("/sanat-muzik", response_class=HTMLResponse)
async def r_sanat(request: Request, db: Session = Depends(get_db)):
    return await category_page("sanat-muzik", request, db)

@router.get("/kocluk-kisisel-gelisim", response_class=HTMLResponse)
async def r_kocluk(request: Request, db: Session = Depends(get_db)):
    return await category_page("kocluk", request, db)

@router.get("/saglik-merkezleri", response_class=HTMLResponse)
async def r_saglik(request: Request, db: Session = Depends(get_db)):
    return await category_page("saglik", request, db)

@router.get("/rehabilitasyon", response_class=HTMLResponse)
async def r_rehab(request: Request, db: Session = Depends(get_db)):
    return await category_page("rehabilitasyon", request, db)

@router.get("/cocuk-aile-hizmetleri", response_class=HTMLResponse)
async def r_cocuk(request: Request, db: Session = Depends(get_db)):
    return await category_page("cocuk-aile", request, db)

@router.get("/kurumsal-danismanlik", response_class=HTMLResponse)
async def r_kurumsal(request: Request, db: Session = Depends(get_db)):
    return await category_page("kurumsal", request, db)

@router.get("/saglik-medikal", response_class=HTMLResponse)
async def r_medikal(request: Request, db: Session = Depends(get_db)):
    return await category_page("saglik-medikal", request, db)

@router.get("/otopark", response_class=HTMLResponse)
async def r_otopark(request: Request, db: Session = Depends(get_db)):
    return await category_page("otopark", request, db)

@router.get("/rent-a-car", response_class=HTMLResponse)
async def r_rent_a_car(request: Request, db: Session = Depends(get_db)):
    return await category_page("rent-a-car", request, db)

# ── HİZMET KISA URL'LERİ ────────────────────────────────────────────────────
@router.get("/sac-kesimi", response_class=HTMLResponse)
async def r_sac_kesimi(request: Request, db: Session = Depends(get_db)):
    return await service_page("sac-kesimi", request, db)

@router.get("/fon", response_class=HTMLResponse)
async def r_fon(request: Request, db: Session = Depends(get_db)):
    return await service_page("fon", request, db)

@router.get("/sac-boyama", response_class=HTMLResponse)
async def r_sac_boyama(request: Request, db: Session = Depends(get_db)):
    return await service_page("sac-boyama", request, db)

@router.get("/gelin-basi", response_class=HTMLResponse)
async def r_gelin_basi(request: Request, db: Session = Depends(get_db)):
    return await service_page("gelin-basi", request, db)

@router.get("/rofle", response_class=HTMLResponse)
async def r_rofle(request: Request, db: Session = Depends(get_db)):
    return await service_page("rofle", request, db)

@router.get("/brezilya-fonu", response_class=HTMLResponse)
async def r_brezilya_fonu(request: Request, db: Session = Depends(get_db)):
    return await service_page("brezilya-fonu", request, db)

@router.get("/perma", response_class=HTMLResponse)
async def r_perma(request: Request, db: Session = Depends(get_db)):
    return await service_page("perma", request, db)

@router.get("/sakal-tirazi", response_class=HTMLResponse)
async def r_sakal_tirazi(request: Request, db: Session = Depends(get_db)):
    return await service_page("sakal-tirazi", request, db)

@router.get("/cocuk-tirazi", response_class=HTMLResponse)
async def r_cocuk_tirazi(request: Request, db: Session = Depends(get_db)):
    return await service_page("cocuk-tirazi", request, db)

@router.get("/kas-alma", response_class=HTMLResponse)
async def r_kas_alma(request: Request, db: Session = Depends(get_db)):
    return await service_page("kas-alma", request, db)

@router.get("/makyaj", response_class=HTMLResponse)
async def r_makyaj(request: Request, db: Session = Depends(get_db)):
    return await service_page("makyaj", request, db)

@router.get("/ipek-kirpik", response_class=HTMLResponse)
async def r_ipek_kirpik(request: Request, db: Session = Depends(get_db)):
    return await service_page("ipek-kirpik", request, db)

@router.get("/jel-tirnak", response_class=HTMLResponse)
async def r_jel_tirnak(request: Request, db: Session = Depends(get_db)):
    return await service_page("jel-tirnak", request, db)

@router.get("/protez-tirnak", response_class=HTMLResponse)
async def r_protez_tirnak(request: Request, db: Session = Depends(get_db)):
    return await service_page("protez-tirnak", request, db)

@router.get("/masaj", response_class=HTMLResponse)
async def r_masaj(request: Request, db: Session = Depends(get_db)):
    return await service_page("masaj", request, db)

@router.get("/sauna", response_class=HTMLResponse)
async def r_sauna(request: Request, db: Session = Depends(get_db)):
    return await service_page("sauna", request, db)

@router.get("/hamam", response_class=HTMLResponse)
async def r_hamam(request: Request, db: Session = Depends(get_db)):
    return await service_page("hamam", request, db)

@router.get("/solaryum", response_class=HTMLResponse)
async def r_solaryum2(request: Request, db: Session = Depends(get_db)):
    return await service_page("solaryum", request, db)

@router.get("/agda", response_class=HTMLResponse)
async def r_agda(request: Request, db: Session = Depends(get_db)):
    return await service_page("agda", request, db)

@router.get("/dovme", response_class=HTMLResponse)
async def r_dovme2(request: Request, db: Session = Depends(get_db)):
    return await service_page("kalici-dovme", request, db)

@router.get("/piercing", response_class=HTMLResponse)
async def r_piercing(request: Request, db: Session = Depends(get_db)):
    return await service_page("piercing", request, db)

@router.get("/pilates", response_class=HTMLResponse)
async def r_pilates(request: Request, db: Session = Depends(get_db)):
    return await service_page("pilates", request, db)

@router.get("/fitness", response_class=HTMLResponse)
async def r_fitness(request: Request, db: Session = Depends(get_db)):
    return await service_page("fitness", request, db)

@router.get("/cilt-bakimi", response_class=HTMLResponse)
async def r_cilt_bakimi(request: Request, db: Session = Depends(get_db)):
    return await service_page("cilt-bakimi", request, db)

@router.get("/sac-bakimi", response_class=HTMLResponse)
async def r_sac_bakimi(request: Request, db: Session = Depends(get_db)):
    return await service_page("sac-bakimi", request, db)
