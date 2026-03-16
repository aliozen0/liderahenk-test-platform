# UI Data Flow Contract

Bu sozlesme, stock Lider UI'nin platform tarafindan nasil beslenmesi gerektigini tanimlar.

## Temel Ilke

UI patch ile "duzeltilmez". UI'nin dogru davranmasi icin:

- dogru LDAP kokleri
- dogru endpoint semantigi
- dogru startup order
- dogru websocket proxy

saglanir.

## Tree Surface Mapping

| UI Yuzeyi | Veri Kaynagi | Root | Not |
| --- | --- | --- | --- |
| User tree | LDAP user endpoints | `user_root` | sadece kullanici ve OU |
| User group tree | LDAP group endpoints | `user_group_root` | user add/remove burada |
| Computer tree | LDAP + domain state | `agent_root` | sag tik menusu `type=AHENK` ile acilir |
| Computer group tree | LDAP group endpoints | `agent_group_root` | policy assignment hedefi |

## State Rules

- `selectedEntry.uid` yalnizca leaf identifier tasir.
- `selectedEntry.distinguishedName` LDAP navigation icin kullanilir.
- User create sonrasi refresh user tree uzerinden yapilir; user-group picker kendi cache'ini ayri tutamaz.
- Computer tree node type `AHENK` veya `WINDOWS_AHENK` olmadan task/policy menusu acilmis sayilmaz.

## Anti-Patterns

- user tree ve computer tree icin ayni generic root kullanmak
- context-menu bos geldiginde UI patch ile menu doldurmak
- backend count patch'i ile stale UI state gizlemek

## Acceptance

- user create -> user tree'de gorunmeli
- user add to group -> user group member list ve picker ayni state'i gostermeli
- agent sag tik -> stock menu acilmali
- script task ve script policy stock ekranlardan gonderilebilmeli
