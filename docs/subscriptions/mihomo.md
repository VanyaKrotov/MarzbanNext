# MIHOMO: YAML-конфигурация

Источник: Remnawave backend **3.4.5**, коммит `010b365ab1fabea01192b5e6ade4e98e66ee1dbd`.
Предобработка: [common.md](common.md); ветка Stash: [stash.md](stash.md).

## Исходники и интерфейс

Файл: [src/modules/subscription-template/generators/mihomo.generator.service.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription-template/generators/mihomo.generator.service.ts).

| Методы / константы | Строки | Назначение |
| --- | --- | --- |
| XHTTP_FIELD_MAP, XMUX_FIELD_MAP | 92–119 | Таблицы XHTTP-переименований |
| generateConfig | 131–173 | Выбор MIHOMO/STASH, фильтры, pipeline |
| buildProxyNode, buildBaseProxyNode | 175–222 | Обычный proxy, mapper |
| applyProtocolFields, applySecurityFields | 228–308 | Credentials, TLS/Reality |
| resolveFingerprint, resolveClashNetwork, applyTransportOpts | 310–373 | Network и fingerprint |
| buildWsOpts, buildTcpOpts, buildGrpcOpts | 375–432 | WS/Upgrade/TCP/gRPC |
| buildXhttpOpts, buildXhttpReuseSettings, buildXhttpDownloadSettings | 434–562 | XHTTP extra/download/xmux |
| renderConfig, resolveGroupRemarks, buildProxyProviders | 564–664 | Шаблон, группы, providers |
| buildHysteria2Node и helpers | 666–796 | Hysteria2, QUIC, obfs |

Вход: hosts, isStash=false, isExtendedClient=false, overrideTemplateName.
Один YAML-документ, Content-Type text/yaml, сериализация js-yaml.dump.
Здесь MIHOMO-ветка; Stash вызывает тот же код с другими flags.

## Фильтрация

Загружается template type MIHOMO. Root template.remnawave.includeHiddenHosts ?? false
определяет допуск скрытых хостов. Входной порядок сохраняется.

1. isHidden исключается, если includeHiddenHosts falsy.
2. excludeFromSubscriptionTypes containing MIHOMO → исключается.
3. transport=kcp → исключается. UNSUPPORTED_PROTOCOLS пустой.
4. buildProxyNode возвращает null для неподдержанного протокола/несогласованной hysteria-пары.

Стандартная публичная MIHOMO-подписка запрашивает hidden hosts из БД, поэтому
includeHiddenHosts=true действительно может включить их. Для прямого вызова SQL-фильтров нет.
isDisabled здесь не проверяется. Ошибка любого host/build/template/render в общем pipeline
даёт `''`; per-host try/catch в Mihomo builder нет.

## Общие поля proxy

Для protocol != hysteria:

```ts
const node: ProxyNode = {
    name: host.finalRemark,
    type: this.resolveClashType(host.protocol),
    server: host.address,
    port: host.port,
    network: this.resolveClashNetwork(host),
    udp: true,
    'ip-version': host.clientOverrides.mihomoIpVersion ?? undefined,
};
```

shadowsocks переименовывается в ss; остальные protocol names сохраняются.
ip-version отсутствует при null, иначе передаётся как есть. Network tcp+HTTP header → http,
httpupgrade → ws, остальные transport names неизменны.

| Protocol | Поля |
| --- | --- |
| vless | uuid=id; packet-encoding=xudp всегда; flow только при xtls-rprx-vision; encryption только truthy и != none |
| trojan | password |
| shadowsocks | password, cipher=method, udp-over-tcp=uot, udp-over-tcp-version=uotVersion, включая false/default |
| hysteria | Отдельный builder ниже |
| Неизвестный | null |

После protocol → security → transport добавить client-fingerprint, затем smux,
затем extended description. smux копируется из host.mux.smux при непустом mux и наличии
ключа smux, **без проверки enabled/валидности**. Не-smux Xray mux-поля игнорируются.
isExtendedClient + description → UTF-8 decode Base64, записать node.serverDescription.
Последним применить mapper.mihomo ко всему proxy, включая Hysteria2.

## TLS / Reality

| Security | Поля |
| --- | --- |
| tls | tls=true; trojan: sni=serverName ?? ''; остальные: servername=serverName ?? ''; truthy alpn.split(',') без trim; skip-cert-verify=true при truthy pin и type != ss |
| reality | tls=true; sni для trojan, servername для остальных; при publicKey truthy reality-opts={public-key, short-id}; optional support-x25519mlkem768=true |
| none | Security-поля не добавляются |

Reality short-id записывается даже при пустой строке, если public-key есть. При отсутствии
publicKey весь reality-opts отсутствует, включая support flag. Flag берётся из
host.clientOverrides.mihomoX25519. ML-DSA, spiderX и ALPN Reality стандартный builder не пишет.
SS с TLS сохраняет tls/servername/alpn, но pin не включает skip-cert-verify для SS.
Для остальных tls pin только отключает verify; сам hash не переносится.

Обычный client-fingerprint всегда добавляется, включая security=none:
lowercase исходного fingerprint → первое имя из FINGERPRINTS, содержащееся в строке,
иначе chrome. Порядок: randomized, android, firefox, chrome, safari, edge, ios, qq, 360, random.
Это substring search, не точное сравнение и не сохранение произвольного fingerprint.

## WS и HTTPUpgrade

`buildWsOpts(path, host, headers, isHttpUpgrade)`:

1. path=rawPath ?? ''. Если содержит точную `?ed=`, split по ней, взять первые две части;
   сохранить первую как path; во второй взять часть до `/`, parseInt без явного radix.
   NaN → не добавлять max-early-data, иначе добавить, включая 0/отрицательное число.
   early-data-header-name=Sec-WebSocket-Protocol добавляется даже при NaN.
2. Непустой path записать.
3. headers={Host:host} при truthy host, иначе {}.
4. Если raw headers != null, spread поверх: исходный headers.Host **перекрывает** host override.
   Заголовки не фильтруются по типам или регистру.
5. HTTPUpgrade добавляет v2ray-http-upgrade=true и v2ray-http-upgrade-fast-open=true.

Результат всегда непустой из-за headers={}, поэтому ws-opts присутствует даже при пустом path/host.
HTTPUpgrade тоже сериализуется в network=ws/ws-opts.
heartbeatPeriod, не относящиеся к early data поля WS здесь не переносятся.

## TCP и gRPC

TCP buildTcpOpts возвращает `{}`: tcp/http-opts не добавляются даже для camouflage.
Сам network=http может присутствовать, но request headers/path из TCP в YAML теряются.
gRPC добавляет grpc-opts.grpc-service-name=serviceName ?? ''. authority и multiMode игнорируются.

## XHTTP

Network=xhttp, результат в xhttp-opts. Truthy path, host, mode → одноимённые поля.
extra отсутствует → только эти поля. Truthy extra.headers → headers как есть.
Затем переименование по таблице. Проверка — `!== undefined`, поэтому false, 0, null
тоже записываются; в строковых полях null превращается в строку `null`.

| extra key | xhttp-opts key | Приведение String |
| --- | --- | --- |
| noGRPCHeader | no-grpc-header | Нет |
| xPaddingBytes | x-padding-bytes | Да |
| xPaddingObfsMode | x-padding-obfs-mode | Нет |
| xPaddingKey | x-padding-key | Нет |
| xPaddingHeader | x-padding-header | Нет |
| xPaddingPlacement | x-padding-placement | Нет |
| xPaddingMethod | x-padding-method | Нет |
| uplinkHTTPMethod | uplink-http-method | Нет |
| sessionIDPlacement | session-placement | Нет |
| sessionIDKey | session-key | Нет |
| sessionIDTable | session-table | Нет |
| sessionIDLength | session-length | Да |
| seqPlacement | seq-placement | Нет |
| seqKey | seq-key | Нет |
| uplinkDataPlacement | uplink-data-placement | Нет |
| uplinkDataKey | uplink-data-key | Нет |
| uplinkChunkSize | uplink-chunk-size | Нет |
| scMaxEachPostBytes | sc-max-each-post-bytes | Нет |
| scMinPostsIntervalMs | sc-min-posts-interval-ms | Нет |
| scStreamUpServerSecs | sc-stream-up-server-secs | Да |

Truthy object extra.xmux → reuse-settings, используя таблицу:

| xmux key | reuse-settings key | String |
| --- | --- | --- |
| maxConnections | max-connections | Да |
| maxConcurrency | max-concurrency | Да |
| cMaxReuseTimes | c-max-reuse-times | Да |
| hMaxRequestTimes | h-max-request-times | Да |
| hMaxReusableSecs | h-max-reusable-secs | Да |
| hKeepAlivePeriod | h-keep-alive-period | Нет |

Объект {} truthy → может появиться reuse-settings={}. Unknown extra keys игнорируются.

### downloadSettings

Truthy object extra.downloadSettings → download-settings:

- truthy address → server, port → port.
- security=tls/reality → tls=true.
- При таком security ds.tlsSettings читается **в обеих ветках**: truthy serverName →
  servername, fingerprint → client-fingerprint без нормализации, alpn → как есть,
  allowInsecure → skip-cert-verify=true.
- При security=reality и truthy realitySettings: truthy publicKey/shortId →
  reality-opts.public-key/short-id; host.mihomoX25519 → support-x25519mlkem768=true.
  Пустой reality-opts не добавляется. Reality serverNames не заменяет servername здесь.
- Truthy ds.xhttpSettings: truthy path, host, headers копируются; object extra.xmux
  внутри него → reuse-settings по таблице выше.

Download ветка не применяет целиком XHTTP_FIELD_MAP, не переносит download mode и не
выводит все поля security/transport. Ни рекурсивного downloadSettings, ни автоматического
расчёта public keys в downloadSettings нет: они должны уже быть клиентскими значениями.

## Hysteria2

protocol=hysteria требует transport=hysteria. База: name, type=hysteria2, server, port,
udp=true, password=transportOptions.auth. Обычные network, ip-version, smux и default
client-fingerprint здесь не добавляются.

Из streamOverrides.finalMask.quicParams:

| Поле | YAML |
| --- | --- |
| brutalUp | up=String(value), если truthy |
| brutalDown | down=String(value), если truthy |
| udpHop.ports | ports=String(value), если truthy; без проверки диапазонов |
| udpHop.interval | hop-interval=String(value), если truthy; без добавления единиц |
| bbrProfile | bbr-profile как есть, если truthy |

congestion и другие QUIC-поля не копируются.

Obfs: найти **первый валидный** элемент finalMask.udp (array), type=salamander,
settings object, password непустая string, packetSize отсутствует либо string/number.
Если packetSize falsy → obfs=salamander, obfs-password=password.
Если truthy → obfs=gecko, password тот же, packetSize разбирается parseIntRangeUtil,
truthy from/to → obfs-min-packet-size / obfs-max-packet-size.
Даже invalid truthy range может дать gecko без size limits. packetSize=null делает
элемент невалидным и позволяет выбрать следующий.

Range helper: split('-',2), одиночное значение даёт одинаковые границы; Number(part),
целое >=0; отсутствующая/пустая часть → null; границы меняются местами при from>to.
Это не parseInt: `1200x` invalid, scientific notation/hex могут быть Number-compatible.

При security=tls: truthy serverName → sni; pin → skip-cert-verify=true; fingerprint →
client-fingerprint **без lowercase/нормализации**; alpn → split(',') без trim.
При security=none/reality TLS-поля не добавляются. Extended description декодируется
как у обычного proxy, затем mapper.mihomo применяется последним.

## Сборка YAML-шаблона

Top-level remnawave удаляется. Остальные поля шаблона сохраняются shallow spread.
proxies = template.proxies (только если array) + generated proxies.
proxy-groups = template.proxy-groups (только если array, иначе []) с обработкой каждой группы.
Новые группы и routing rules генератор не изобретает; `data.rules` фактически не используется.

Для каждой группы убрать служебный remnawave и определить список generated names:

1. include-proxies === false → [].
2. Иначе select-random-proxy === true → один случайный name или [] при пустом списке.
3. Иначе shuffle-proxies-order === true → shuffle всех names.
4. Иначе все names в исходном порядке.

group.proxies = исходный group.proxies (только array) + выбранные names. Нет dedup,
старые proxies не заменяются. Names берутся из **host.finalRemark**, даже если mapper
изменил node.name; группа тогда может ссылаться на уже отсутствующее имя.

Providers: для каждого template.proxy-providers entry с truthy remnawave убрать его;
если include-proxies === true, заменить payload массивом **только generated proxies**.
Исходный payload и template.proxies туда не добавляются. Без служебного remnawave
provider сохраняется как есть. Прочие поля providers остаются.

Итог dump(finalConfig). YAML comments/formatting исходного шаблона не сохраняются.
Aliases и quoting зависят от js-yaml. Для Python сначала требовать эквивалентную структуру,
а byte parity YAML оформлять как отдельное требование.

## Пример

Для Demo из [xray-base64.md](xray-base64.md) generated proxy имеет структуру:

```yaml
name: Demo
type: vless
server: vpn.example.com
port: 443
network: ws
udp: true
uuid: 11111111-1111-4111-8111-111111111111
packet-encoding: xudp
tls: true
servername: cdn.example.com
alpn: [h2, http/1.1]
ws-opts:
  path: /ws
  headers:
    Host: cdn.example.com
  max-early-data: 2048
  early-data-header-name: Sec-WebSocket-Protocol
client-fingerprint: chrome
```

Это proxy-фрагмент, не полный шаблон. Пример XHTTP extra:

```json
{
  "noGRPCHeader": false,
  "xPaddingBytes": "100-200",
  "sessionIDLength": 16,
  "xmux": {"maxConnections": 4, "hKeepAlivePeriod": 30}
}
```

Порождает xhttp-opts keys no-grpc-header=false, x-padding-bytes="100-200",
session-length="16", reuse-settings.max-connections="4", h-keep-alive-period=30.

## Python-перенос и проверочные сценарии

Разделить build_base_proxy, build_hysteria2_proxy, build_ws_opts, map_xhttp_extra,
map_download_settings, render_groups, render_providers. Общую YAML-сборку с Clash
переиспользовать только с явными различиями: root remnawave, headers, providers, mapper.

Проверить:

1. VLESS none/custom encryption, flow='', vision; Trojan и SS uot=false/version.
2. TLS pin для SS и non-SS; Reality с пустым/непустым publicKey, X25519 flag, empty short-id.
3. Нормализация uppercase fingerprint обычного proxy и отсутствие её у Hysteria2/download.
4. WS ed valid/0/negative/invalid/hex, raw headers.Host перекрывает resolved host.
5. TCP camouflage loss; gRPC authority/multiMode loss.
6. Каждое XHTTP_FIELD_MAP/XMUX_FIELD_MAP поле, включая 0/false/null и string coercion.
7. Download TLS/Reality, tlsSettings в Reality, nested reuse settings и неучтённые extra keys.
8. Hysteria2 QUIC строки, range swap, packetSize='bad', 0, null, первый невалидный mask.
9. Hidden default/enable, excluded MIHOMO, KCP skip; ошибка одного host → вся строка пустая.
10. Группы include/random/shuffle priority, старые names, mapper меняет node.name.
11. Providers replace payload, preserve untouched providers, remove root remnawave.
12. smux без enabled/с false; extended UTF-8 description; mapper deep paths.
