# LiderAhenk Test Platform Vizyonu

## Ana Hedef: Bağımsız ve Dışsal Bir Laboratuvar Ortamı

Bu deponun (repo) temel amacı, LiderAhenk’in iç mantığını değiştirerek çalışan özel bir "fork" (çatallanma) oluşturmak **değildir**. Aksine, LiderAhenk’i mümkün olduğunca değiştirmeden, dışarıdan saran ve kapsayan bir test ve laboratuvar platformu olmaktır.

Yani amaç “uygulamayı patch’leyip (yamalayıp) kendimize göre çalıştırmak” değil, “gerçek hayatta bir kurumun LiderAhenk sunucusu ile alt istemciler/sanal makineler (VM) kurduğu ortamı tek komutla, tekrar üretilebilir (reproducible), geliştirici dostu ve versiyonlar arası geçişlere dayanıklı şekilde simüle etmektir”.

## Temel Prensipler

1. **Sürüm Bağımsızlığı:** Platform, belirli bir LiderAhenk sürümüne sıkı sıkıya bağlı olmamalıdır. Yeni bir `liderapi`, `liderui`, `lider-core` veya `ahenk` sürümü geldiğinde, projenin iç kodlarında büyük değişiklikler yapmadan (yeniden oymadan) çalışabilmelidir.
2. **Modülerlik ve Dışsallık:** Sistem olabildiğince dışsal, modüler olmalı ve Open/Closed prensibine (Gelişime açık, değişime kapalı) uyumlu kurulmalıdır. 
3. **SOLID Yaklaşımı:** 
    * Yukarı akış (upstream) ürün kapalı kalmalıdır.
    * Test platformu bu ürünü dışarıdan genişletmelidir; orchestrasyon, provizyonlama (provisioning), ayar enjeksiyonu (config injection), gözlemlenebilirlik (observability), hazır veri, VM/konteyner yönetimi ve kabul testleri (acceptance tests) gibi özellikleri dış bir katman olarak sunmalıdır.

## Özet

Hedefimiz "patch'lenmiş" (yamalanmış) bir ürün yaratmak değil, gerçek bir LiderAhenk kurulumunu sanki sanal makinelere kuruyormuş gibi ayağa kaldıran, ancak bunu tam otomatik ve esnek bir platform katmanı olarak sağlayan bir araç geliştirmektir.

## Somut Platform Yüzeyi

Bu vizyonun repodaki resmi karşılıkları şunlardır:

- `platform/bootstrap/bootstrap-manifest.yaml`
- `platform/contracts/directory-model.yaml`
- `platform/contracts/ldap-roots.yaml`
- `platform/contracts/registration-state-machine.yaml`
- `platform/contracts/ui-data-flow.md`
- `platform/contracts/websocket-contract.md`
- `platform/services/registration-orchestrator/`

Ayrıca iki resmi çalışma profili vardır:

- `dev-fast`: hızlı geliştirme ve smoke testi
- `dev-fidelity`: stock kurulum paritesine en yakın kabul profili
