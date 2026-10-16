# XRAY_JSON: клиентские конфигурации Xray

Источник: Remnawave backend **3.4.5**, коммит `010b365ab1fabea01192b5e6ade4e98e66ee1dbd`.
Предобработка: [common.md](common.md). Навигация: [README.md](README.md).

## Исходники и контракт

Основной файл: [src/modules/subscription-template/generators/xray-json.generator.service.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription-template/generators/xray-json.generator.service.ts).
Типы: [generators/interfaces/xray-json-config.interface.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription-template/generators/interfaces/xray-json-config.interface.ts).
Injector schema: [libs/contract/models/xray-json-advanced/remnawave-injector.schema.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/libs/contract/models/xray-json-advanced/remnawave-injector.schema.ts).

| Код | Назначение |
| --- | --- |
| PROTOCOL_BUILDERS / TRANSPORT_BUILDERS, строки 48–129 | Протокольные settings и transport settings |
| buildTcpSettings / buildTlsSettings / buildRealitySettings, 131–196 | Security и TCP |
| generateConfig, 204–256 | Выбор шаблона, фильтрация, JSON-массив |
| buildOutboundConfig / buildOutbound, 258–304 | Обычная сборка outbound, mux, mapper |
| buildTransportEntry / buildProtocolSettings / buildSecurityEntry / buildStreamSettings, 306–365 | Сборка streamSettings |
| buildTaggedOutbounds / resolveHosts / applyRemnawaveInjector, 367–493 | Внедрение нескольких хостов |

Вход generateConfig: hosts, isExtendedClient, overrideTemplateName и
ignoreHostXrayJsonTemplate=false. Выход — compact JSON **массив** полных конфигураций,
Content-Type application/json. В нормальной ветке один host → один config;
inbounds, DNS, routing и служебные outbounds происходят из клиентского шаблона.
Пустой успешный результат → `[]`, ошибка общего try/catch → `''`.

## Порядок генерации и шаблон

1. Загрузить общий XRAY_JSON template по overrideTemplateName/Default.
   Загрузка происходит даже при hosts=[] и даже если у всех hosts собственные templates.
2. Для каждого host пропустить isHidden=true и exclusion `XRAY_JSON`.
3. Если ignoreHostXrayJsonTemplate=true, взять общий template; иначе
   `host.clientOverrides.xrayJsonTemplate ?? templateContent`.
   Это nullish choice: пустой JS object `{}` выигрывает у общего шаблона.
4. Truthy baseTemplate.remnawave включает injector-ветку, иначе обычную.
5. Обычная ветка строит outbound с tag=proxy, ставит его **перед** template.outbounds.
6. Конфиги остаются в порядке hosts, затем JSON.stringify(configs, null, 0).

```ts
configs.push({
    ...baseTemplate,
    outbounds: [...outboundConfig.outbounds, ...(baseTemplate.outbounds ?? [])],
    remarks: outboundConfig.remarks,
    meta: outboundConfig.meta,
});
```

Shallow merge, не deep merge. remarks всегда заменяется finalRemark. В обычной ветке
template.meta заменяется outboundConfig.meta; если extended description отсутствует,
это undefined, и meta исчезает из JSON, даже если присутствовал в template.
Обычная ветка допускает отсутствие/null template.outbounds через `?? []`.
Duplicate tags в служебных и сгенерированных outbounds не проверяются.

## Построение outbound

```ts
const outbound: Outbound = {
    tag,
    protocol: host.protocol,
    settings: this.buildProtocolSettings(host),
    streamSettings: this.buildStreamSettings(host),
};
```

| Protocol | settings |
| --- | --- |
| vless | `vnext=[{address,port,users:[{id,encryption: encryption || 'none',flow}]}]` |
| trojan | `servers=[{address,port,password}]` |
| shadowsocks | `servers=[{address,port,password,method,uot,UoTVersion:uotVersion}]` |
| hysteria | `{address,port,version:2}` |

Ключ Shadowsocks пишется именно **`UoTVersion`**. VLESS flow присутствует даже при `''`.
Hysteria использует Xray protocol=hysteria, а не имя hysteria2 из других клиентов.
Здесь нет unsupported sets; проверка совместимости произвольных сочетаний отсутствует.

Если host.mux непустой object, удалить из него top-level smux; если остались ключи,
записать outbound.mux. Объект только с smux не создаёт mux. Исходный host.mux не мутируется.
Затем применить `mapper.xrayJson` ко **всему outbound**. Mapper может переопределить
tag, settings, streamSettings и mux; он не применяется к template.inbounds/routing.

## Transport → streamSettings

`network=host.transport`, поэтому исходный raw после resolver записывается как tcp.

| Transport | Поле и состав |
| --- | --- |
| tcp | tcpSettings: header целиком, если он есть; иначе `{}` |
| ws | wsSettings: path, host, headers как `{...headers}`; heartbeatPeriod только если != null |
| httpupgrade | httpupgradeSettings: path, host, headers как `{...headers}` |
| xhttp | xhttpSettings: mode и host всегда; path/extra только truthy |
| grpc | grpcSettings: serviceName, authority, multiMode=!!multiMode |
| kcp | kcpSettings: mtu=clientMtu, tti=clientTti, congestion |
| hysteria | hysteriaSettings: version=2, auth |

WS/httpupgrade path и gRPC serviceName/authority могут быть JSON null — они не удаляются.
Headers=null превращаются в `{}`. heartbeatPeriod=0 сохраняется. Early data `?ed=`
в path не разбирается. TCP header.http включает нормализованный request из resolver;
поля ответа могли быть удалены ещё на предыдущем этапе.

В streamSettings после transport/security добавляются truthy
`streamOverrides.sockopt` → sockopt, `streamOverrides.finalMask` → **finalmask**.
Регистр finalmask отличается от внутреннего finalMask.

## TLS

При security=tls записываются security='tls' и tlsSettings.

| Поле tlsSettings | Условие / значение |
| --- | --- |
| serverName | Всегда `opts.serverName || ''` |
| enableSessionResumption | Всегда bool из resolver |
| fingerprint | Если `opts.fingerprint !== ''`; null сохранится, undefined исчезнет при JSON serialization |
| alpn | При truthy строке split(',') **без trim** |
| pinnedPeerCertSha256 | При truthy, исходная строка |
| verifyPeerCertByName | При truthy |
| echForceQuery, echConfigList, echSockopt, cipherSuites | Каждое при truthy |

allowInsecure/insecure стандартный генератор не добавляет. Для этих дополнительных
полей можно использовать mapper. Не следует переносить семантику insecure из YAML/sing-box
в Xray JSON: здесь pinned certificate копируется как сертификатный pin.

## Reality

При security=reality: security='reality', realitySettings.serverName всегда;
publicKey, mldsa65Verify, shortId, spiderX — только truthy; fingerprint если !== ''.
Ключи/seed получены resolver по правилам [common.md](common.md), privateKey сюда не копируется
стандартным builder. Пустой shortId не записывается. ALPN в этой ветке нет.
При security=none записывается только security='none', без security settings.

## Injector: несколько хостов в одном конфиге

Truthy top-level template.remnawave переключает генерацию, даже `{}` (JS truthy).
Служебный remnawave из результата удаляется через destructuring.

Поля injector:

| Поле | Значение |
| --- | --- |
| addVirtualHostAsOutbound | При true добавить outbound текущего recipient host с tag=proxy |
| injectHosts | Массив entries, каждое выбирает хосты и назначает tags |

Если нет truthy injectHosts и нет addVirtualHostAsOutbound, вернуть null и пропустить
config. Пустой массив injectHosts=[] truthy: config может состоять только из служебных
template.outbounds. Отдельного fallback к обычной ветке не происходит.

Recipient — текущий видимый, не исключённый из XRAY_JSON host. Источник candidates:

| selectFrom | Выбор |
| --- | --- |
| Не задан / HIDDEN | Только isHidden=true |
| NOT_HIDDEN | Только isHidden=false |
| ALL | Все входные resolved hosts |

Во всех случаях исключаются записи с uuid recipient. Здесь **не повторяется** проверка
excludeFromSubscriptionTypes. Поэтому hidden/excluded host может быть внедрён как outbound,
хотя отдельный config для него не создавался. Общие SQL/tag/fallback-фильтры уже применены.

| selector.type | Алгоритм и порядок |
| --- | --- |
| uuids | Пройти selector.values по порядку, для каждого взять первый candidate с этим UUID; missing пропустить; повтор UUID повторяет outbound |
| remarkRegex | new RegExp(pattern), regex.test(finalRemark); сохраняет порядок candidates |
| sameTagAsRecipient | Непустые tags с обеих сторон и хотя бы одно точное пересечение |
| tagRegex | Хотя бы один tag подходит regex, порядок candidates |

Regex invalid → лог и пустой выбор, остальные entries продолжаются. Передаётся строка
pattern без отдельного flags; ECMAScript syntax может отличаться от Python re.

Tags для каждого entry:

1. useHostRemarkAsTag=true → finalRemark.
2. Иначе useHostTagAsTag=true → первый metadata.tags либо finalRemark.
3. Иначе prefix=tagPrefix ?? 'proxy': первый prefix, второй prefix-2, третий prefix-3.

Нумерация начинается заново в каждом entry. Дубли tag/хоста между entries и virtual host
не устраняются. Mapper.xrayJson применяется к каждому внедрённому outbound и может
изменить уже назначенный tag. Перезапись tag mapper-ом не синхронизирует routing автоматически.

Порядок полного массива:

```text
[virtual recipient outbound, если включён]
+ [все entries по очереди; хосты внутри entry в порядке selector]
+ [template.outbounds в исходном порядке]
```

Injector использует `...template.outbounds` **без** `?? []`; отсутствие/null массива
приводит к ошибке. Ошибка здесь перехватывается общим generateConfig и обнуляет **всю**
подписку `''`, включая уже построенные configs. В обычной ветке buildOutboundConfig
перехватывает ошибку одного host, логирует и возвращает null — это другая граница ошибок.

Injector сохраняет исходный template.meta, если нет extended description. При наличии
описания перезаписывает meta объектом `{serverDescription: decoded UTF-8}`.

Пример клиентского шаблона injector (UUID ниже вымышленный):

```json
{
  "outbounds": [{"tag": "direct", "protocol": "freedom"}],
  "remnawave": {
    "addVirtualHostAsOutbound": false,
    "injectHosts": [{
      "selectFrom": "HIDDEN",
      "selector": {"type": "sameTagAsRecipient"},
      "tagPrefix": "hop"
    }]
  }
}
```

В template-update API injectHosts entry дополнительно требует хотя бы один из tagPrefix,
useHostRemarkAsTag, useHostTagAsTag и проверяет regex. Runtime builder имеет default proxy,
но это не означает, что API принимает entry без naming option.

## Пример обычного outbound

Для входа Demo из [xray-base64.md](xray-base64.md) генератор создаёт:

```json
{
  "tag": "proxy",
  "protocol": "vless",
  "settings": {
    "vnext": [{
      "address": "vpn.example.com",
      "port": 443,
      "users": [{
        "id": "11111111-1111-4111-8111-111111111111",
        "encryption": "none",
        "flow": ""
      }]
    }]
  },
  "streamSettings": {
    "network": "ws",
    "wsSettings": {"path": "/ws?ed=2048", "host": "cdn.example.com", "headers": {}},
    "security": "tls",
    "tlsSettings": {
      "serverName": "cdn.example.com",
      "enableSessionResumption": false,
      "fingerprint": "chrome",
      "alpn": ["h2", "http/1.1"]
    }
  }
}
```

Это только outbound, не полный HTTP body. Для шаблона `{"outbounds":[]}` полный результат
имеет форму `[{"outbounds":[<outbound>],"remarks":"Demo"}]`.
Полный default template дополнительно сохраняет DNS, routing, SOCKS/HTTP inbounds и
outbounds direct/block. Extended clients получают decoded description в meta.serverDescription.

## Python-перенос и проверки

Предлагаемые функции: build_protocol_settings, build_transport_settings,
build_security_settings, build_outbound, resolve_injected_hosts, render_xray_json.
Различать null/undefined; не добавлять transport-specific filtering из других клиентов.
Строить новые containers, сохраняя template/host неизменными. Поля `meta` в двух ветках
имеют разные правила overwrite, их нельзя объединять общим безусловным update.

Проверочные сценарии:

1. Все четыре протокола × каждый поддерживаемый transport; полный JSON array shape.
2. TLS все optional поля, empty/null fingerprint, ALPN с пробелами, heartbeatPeriod=0.
3. Reality shortId='', publicKey='', mldsa65Verify, sockopt/finalmask.
4. mux только smux, smux+Xray поля, empty mux; mapper после builder.
5. Global vs host template, ignoreHost flag, отсутствующий Default даже при host template.
6. Template.meta: исчезает в обычной ветке без description, сохраняется в injector.
7. Hidden/excluded recipients не создают config; те же записи могут стать injected outbounds.
8. Каждый selector, uuids order/duplicates, invalid regex, sameTag intersection.
9. Naming priority, prefix-2, повторные entries и tag collisions.
10. remnawave={}, injectHosts=[], no template.outbounds; ошибка одного обычного host
    против ошибки injector, обнуляющей всю подписку.
11. Пустой успешный массив `[]` против ошибочной пустой строки `''`.
