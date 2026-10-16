# STASH: ветка общего Mihomo-генератора

Источник: Remnawave backend **3.4.5**, коммит `010b365ab1fabea01192b5e6ade4e98e66ee1dbd`.
Общие правила: [common.md](common.md). Полная спецификация shared builder: [mihomo.md](mihomo.md).
Этот документ вместе с `mihomo.md` образует спецификацию Stash; самостоятельного
`stash.generator.service.ts` в исходнике нет.

## Исходники и вызов

- [render-templates.service.ts, ветка STASH](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription-template/render-templates.service.ts#L82-L91)
- [mihomo.generator.service.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription-template/generators/mihomo.generator.service.ts)
- [default-templates.ts, DEFAULT_TEMPLATE_STASH](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription-template/constants/default-templates.ts)

```ts
subscription: await this.mihomoGeneratorService.generateConfig(
    formattedHosts,
    true,
    false,
    srrContext.overrideTemplateName,
),
```

Аргументы: isStash=true, isExtendedClient=false. Content-Type text/yaml.
Результат — один YAML-документ из STASH-шаблона, а не MIHOMO/CLASH-шаблона.

## Отличия от MIHOMO

| Аспект | STASH |
| --- | --- |
| templateType | STASH |
| excludeFromSubscriptionTypes | Проверяется STASH; exclusion MIHOMO сам по себе не исключает |
| transport=xhttp | Всегда исключается до builder |
| transport=kcp | Исключается общей константой |
| extended description | Выключено dispatcher-ом, даже для extended User-Agent |
| mapper | Используется mapper.mihomo; отдельного mapper.stash нет |
| hidden в публичном service | GetHostsForUserQuery возвращает hidden=false для STASH |

Последний пункт важен: shared generator читает template.remnawave.includeHiddenHosts,
но публичный STASH pipeline заранее убирает hidden hosts. Этот флаг не может вернуть
невыбранные SQL записи. При прямом вызове генератора с hidden hosts флаг работает так же,
как у Mihomo. Фильтр isDisabled тоже остаётся на уровне выбора данных.

Остальные части builder **не меняются** при isStash:

- VLESS с packet-encoding=xudp, vision flow и custom encryption; Trojan; SS с UOT;
  Hysteria2 через отдельный builder.
- TLS/Reality, support-x25519mlkem768, нормализация fingerprint обычных proxies.
- WS/HTTPUpgrade headers и early data; TCP camouflage loss; gRPC service name.
- smux передаётся без проверки enabled.
- Hysteria2 QUIC fields и obfs gecko при packetSize — даже если это не подходит
  конкретной версии Stash. Исходник не имеет дополнительных Stash guards.
- Mapper.mihomo после сборки; groups/providers/root remnawave обрабатываются как MIHOMO.

Следовательно не нужно вырезать дополнительное поведение из совместимого порта по
предположению о поддержке Stash. Валидация фактического клиента — отдельный этап.

## Поля и алгоритм

Обычный proxy: name=finalRemark, type protocol (SS→ss), server=address, port,
network по shared conversion, udp=true, optional ip-version; затем protocol/security,
transport, client-fingerprint, optional smux и mapper.mihomo.

VLESS flow выводится только при точном xtls-rprx-vision. Encryption!='none' выводится,
а не фильтруется как в sing-box. Reality public-key из resolver; empty short-id остаётся
в reality-opts при непустом public-key. pin включает skip-cert-verify кроме SS.
WS raw headers могут перекрыть вычисленный Host. HTTPUpgrade — network=ws с двумя
v2ray-http-upgrade flags. KCP и XHTTP не доходят до этих этапов.

Groups: существующие names + generated names, флаги include-proxies=false,
select-random-proxy=true, shuffle-proxies-order=true по этому приоритету.
Providers с include-proxies=true получают payload только generated proxies.
Root remnawave удаляется; остальные root fields сохранены. YAML dump без сохранения comments.
Names групп основаны на host.finalRemark, не на node.name после mapper.

## Default template

Default STASH отличается от Default MIHOMO содержимым, не только именем:

- Группа → Remnawave, type=select, заполняемые proxies.
- mode=rule, log-level=warning.
- DNS default-nameserver/nameserver: 1.1.1.1 и 1.0.0.1.
- script.shortcuts.quic: `network == 'udp' and dst_port == 443`.
- Правило SCRIPT,quic,REJECT; исключения Apple domains/processes, WARP, торрент/download
  приложений, GEOIP,LAN,DIRECT; последнее MATCH,→ Remnawave.
- Здесь не задаются mixed/socks/redir ports как в Default MIHOMO.

Шаблон хранится и может быть изменён пользователем. Переносить полный текст из закреплённого
default-templates.ts, если требуется сохранить defaults; нельзя заменять его Mihomo template.
Script, DNS, rules и пользовательские fields renderer сохраняет без самостоятельной генерации.

## Пример и проверки

WS VLESS Demo из [mihomo.md](mihomo.md) даёт тот же proxy node в Stash. Отличаются template,
format exclusion и flags dispatcher. Если тот же host переключить на XHTTP:
MIHOMO добавит proxy, STASH пропустит его. Если он единственный — вернётся STASH-шаблон
с пустым generated списком; empty-host fallback после этого не запускается.

Предлагаемый Python-интерфейс: `render_mihomo(hosts, template, is_stash=True,
is_extended_client=False)`, сохраняя отдельный STASH response type и template namespace.

Проверить:

1. Одинаковый WS host → одинаковые proxy fields у MIHOMO/STASH.
2. XHTTP/KCP исключаются, VLESS/Hysteria2 допускаются; mapper.mihomo работает.
3. Exclusion STASH действует, MIHOMO не действует; обратный случай для Mihomo.
4. Dispatcher никогда не выводит serverDescription в STASH.
5. Hidden SQL-фильтр против прямого вызова includeHiddenHosts=true.
6. STASH template name/default выбираются независимо от MIHOMO.
7. Providers/groups/remnawave совпадают с shared renderer; правила/script Default сохраняются.
8. Пустой generated список возвращает YAML, ошибка shared builder → `''`.
