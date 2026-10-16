# SINGBOX: JSON-конфигурация sing-box

Источник: Remnawave backend **3.4.5**, коммит `010b365ab1fabea01192b5e6ade4e98e66ee1dbd`.
Исходный комментарий генератора задаёт target **sing-box 1.13.x**; документ описывает
этот код, а не все возможности любых версий sing-box. Предобработка: [common.md](common.md).

## Исходники и интерфейс

Файл: [src/modules/subscription-template/generators/singbox.generator.service.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription-template/generators/singbox.generator.service.ts).

| Методы / константы | Строки | Назначение |
| --- | --- | --- |
| UNSUPPORTED_TRANSPORTS, PROXY_PROTOCOL_TYPES, SELECTOR_TYPES, MULTIPLEX_PROTOCOLS | 104–107 | Ограничения и наборы для групп |
| generateConfig / buildOutbound / buildBaseOutbound | 115–177 | Отбор, builder, mapper |
| applyProtocolFields | 179–217 | Protocol settings |
| applyMultiplex / buildMultiplexConfig / parsePositiveInt | 219–270 | smux → multiplex |
| buildHysteria2Outbound и parsers | 272–353 | Hysteria2, ports, speed, duration |
| applyTransport / build*Transport / buildHeaders | 355–469 | WS/Upgrade/gRPC |
| applySecurity / build*Config / resolveFingerprint | 471–571 | TLS, Reality, QUIC TLS |
| renderConfig | 573–604 | Сборка outbounds, selector/urltest |

Вход: hosts, overrideTemplateName; один compact JSON-object, Content-Type application/json.
Template type SINGBOX. Загрузка шаблона до цикла даже при пустом hosts.
Пустой generated список → шаблон с пересобранными outbounds; ошибка → `''`, не `{}`.

## Фильтры и база outbound

Исключить exclusion SINGBOX и transport kcp/xhttp. isHidden/isDisabled здесь не проверяются;
публичный SINGBOX pipeline заранее выбирает их как false. VLESS custom encryption!=none
дополнительно отбрасывается в protocol builder. Hysteria требует transport=hysteria.
Неизвестный protocol → null. Неподдерживаемые хосты не запускают fallback повторно.

Обычный outbound (protocol != hysteria):

```ts
const config: OutboundConfig = {
    type: host.protocol,
    tag: host.finalRemark,
    server: host.address,
    server_port: host.port,
};
```

Далее protocol → transport → security → multiplex. После полной сборки mapper.singbox
применяется ко всему outbound. Ошибка buildOutbound конкретного host перехватывается
и даёт null без логирования; цикл продолжает остальные. Ошибка шаблона/renderConfig
попадает в общий catch и даёт пустую строку с логом.

## Protocol fields

| Protocol | Поля и условия |
| --- | --- |
| vless | Truthy encryption!='none' → null; uuid=id; flow только vision + transport=tcp + security!=none |
| trojan | password |
| shadowsocks | password, method; при uot truthy network=tcp, udp_over_tcp={enabled:true, version:1 только если uotVersion===1} |
| hysteria | Отдельная ветка ниже с type=hysteria2 |

VLESS encryption ключ в результат не добавляется вообще. Flow в WS/gRPC не выводится,
даже если resolver вычислил vision по инбаунду. Shadowsocks uotVersion=2 не выводит version=2:
version просто отсутствует, используется клиентское поведение по умолчанию.

## Transport

TCP не создаёт поле transport. TCP HTTP camouflage headers/path игнорируются, в том числе
при header.type=http. Неизвестный runtime transport тоже не создаёт поле, если прошёл фильтр.
WS/httpupgrade/gRPC создают отдельный transport object.

### WS

База `{type:'ws'}`. rawPath ?? ''. При точном `?ed=` разделить строку, оставить первую
часть как path, следующую до `/` преобразовать через **Number**, не parseInt.
Если !isNaN → max_early_data, включая 0/дробное/отрицательное/Infinity runtime-значение.
Всегда при наличии `?ed=` → early_data_header_name=Sec-WebSocket-Protocol.
Непустой очищенный path добавить; buildHeaders(rawHeaders, resolvedHost) добавить только
при непустом результате.

Следствия: `?ed=12x` не добавляет число; `?ed=`/`?ed= ` → 0; `?ed=1.5` → 1.5.
Infinity возможен на уровне object, но JSON.stringify превращает non-finite number в null.
Python-порт не должен без отдельного решения запрещать всё, что TS здесь принимает.

### HTTPUpgrade

База `{type:'httpupgrade'}`, truthy path и host — отдельные одноимённые поля.
`?ed=` не разбирается; HTTPUpgrade здесь не эмулируется через WS.
Headers=buildHeaders(rawHeaders, null); все raw Host/header варианты будут удалены.
Специальные v2ray-http-upgrade flags, используемые в YAML, отсутствуют.

### gRPC

`{type:'grpc', service_name: serviceName ?? ''}`. authority и multiMode не выводятся.

### Заголовки и регистр

buildHeaders сначала проходит rawHeaders:

- Если key.toLowerCase()==host и resolvedHost falsy, пропустить.
- Если value не string, пропустить.
- Остальные key/value сохранить с исходным регистром.
- Если resolvedHost truthy, последним записать headers.Host=resolvedHost.

При WS raw `Host` перезаписывается вычисленным host. Raw `host`/`HOST` при truthy host
могут остаться рядом с новым `Host`, потому что target dictionary регистрозависим.
При falsy host все варианты Host удаляются. При HTTPUpgrade это правило используется
с host=null, даже если transport.host задан отдельно.
В Mihomo rawHeaders.Host имеет обратный приоритет — нельзя переиспользовать merge без flags.

## TLS и Reality

TLS: tls.enabled=true всегда; truthy serverName → server_name; truthy fingerprint →
utls={enabled:true,fingerprint:normalize}; truthy pin → insecure=true; truthy alpn →
split(',').map(trim). Пустые элементы после split не фильтруются.
Pin не переносится как hash. ECH, verifyPeerCertByName, session resumption, cipherSuites
и streamOverrides.sockopt/finalMask общего соединения здесь не выводятся.

Reality: tls={enabled:true,reality:{enabled:true}}; truthy serverName → server_name;
publicKey → reality.public_key; shortId → reality.short_id; utls всегда включён,
fingerprint normalized/default chrome. ML-DSA, spiderX, ALPN и support-x25519mlkem768
в эту ветку не копируются.
None: нет поля tls у обычного outbound.

Нормализация fingerprint: первое substring совпадение в FINGERPRINTS, иначе chrome.
**Без toLowerCase**: `FIREFOX` → chrome, `firefox-custom` → firefox. Список и порядок
совпадают с YAML, но case handling отличается.

## smux → multiplex

Для обычного outbound после security вызвать applyMultiplex; если
config.udp_over_tcp.enabled truthy — сразу пропустить multiplex.
Требуется непустой host.mux.smux object и **smux.enabled === true**.

| Вход smux | Выход multiplex |
| --- | --- |
| enabled=true | enabled=true |
| protocol string из h2mux/smux/yamux | protocol |
| max-connections | max_connections, если parsePositiveInt >0 |
| min-streams | min_streams, аналогично |
| max-streams | max_streams, аналогично |
| padding===true | padding=true |
| brutal-opts.enabled===true и оба up/down >0 | brutal={enabled:true,up_mbps,down_mbps} |

parsePositiveInt принимает только number/string; trim → parseInt(...,10) → finite >0.
`'12x'` → 12, 1.9 → 1, `'0x10'` → 0 → отсутствует, bool не допускается.
parseMbps использует тот же алгоритм: `'100 Mbps'` → 100, преобразования единиц нет.
Неизвестные smux и остальные Xray mux поля игнорируются. Только enabled=true уже даёт
`multiplex:{enabled:true}`, без дополнительных полей. Mapper позже может добавить multiplex
даже при UOT, но стандартный builder этого не делает.

## Hysteria2

База: type=hysteria2, tag, server, server_port, password=transportOptions.auth,
tls=buildQuicTlsConfig(host). TLS всегда имеет enabled=true, даже при security=none/reality.
При security=tls добавить truthy server_name, insecure при pin, ALPN split+trim.
uTLS/fingerprint не добавляется к QUIC. Общие transport/multiplex методы не вызываются.

Из streamOverrides.finalMask.quicParams:

- brutalUp/brutalDown → up_mbps/down_mbps через parsePositiveInt; каждая независимо.
- udpHop.ports → parsePortRanges; при непустом списке server_ports.
- Только если server_ports непустой, udpHop.interval → hop_interval через parseDuration.
- bbrProfile/congestion/packetSize и остальные QUIC настройки не выводятся.

### Диапазоны портов

String(value).split(','); каждую часть trim → parseIntRangeUtil (Number integer >=0,
swap при перевёрнутых границах). from=null/0/>65535 пропустить.
end = from, если to=null/>65535; иначе to. Добавить строку `from:end`.
Одиночный 443 → `443:443`; 200-100 → `100:200`; 443-70000 → `443:443`.
Проверка чисел не выполняет dedup и не объединяет пересекающиеся диапазоны.

### Duration

Trim String(value). Если только decimal digits, Number(raw)>0 → raw+'s', иначе null.
Иначе regex `^\d+(\.\d+)?(ns|us|µs|ms|s|m|h)$` → сохранить строку, иначе null.
`0` → отсутствует, но `0s` и `0.0s` → сохраняются. `10` → 10s, `1.5` без suffix → invalid,
`1.5s` valid; `10 sec` invalid. Ведущие нули строки сохраняются.

### Obfs

Первый finalMask.udp элемент type=salamander с truthy settings.password →
obfs={type:'salamander',password}. В отличие от URI, поиск учитывает наличие password.
В отличие от Mihomo, нет строгой проверки типа password/packetSize и нет gecko-ветки.
finalMask целиком в JSON не копируется.

## Полный шаблон и группы

```ts
const allOutbounds = [...(template.outbounds as OutboundConfig[]), ...userOutbounds];
```

Template.outbounds должен быть iterable array: отсутствие/null → общий error/`''`.
Исходные outbounds идут **перед** generated. Это противоположно обычному Xray JSON.
Root DNS/inbounds/route/experimental и другие поля сохраняются shallow spread.

Сначала по allOutbounds **после mapper** собрать:

- urltestTags: type in hysteria2/shadowsocks/trojan/vless.
- selectorTags: те же + urltest.

Затем для каждого outbound удалить top-level remnawave. Если
remnawave.includeProxies===false — сохранить остальные поля, включая старый outbounds.
Иначе type=urltest → **заменить** outbounds=urltestTags;
type=selector → **заменить** outbounds=selectorTags; другие сохранить.
Template proxy outbounds тоже входят в вычисленные lists. Direct/block и selector
не входят автоматически; дубли tag не удаляются. Старые списки selector/urltest не
дополняются, а заменяются. Тип/имя mapper изменяет до вычисления списков, поэтому новые
tag попадут в них (в отличие от YAML groups на основе host.finalRemark).

Root remnawave не удаляется renderer-ом. Только remnawave отдельных outbounds удаляется.
Флаги random/shuffle/inline providers из YAML здесь не реализованы.

Default template включает DNS servers/rules, TUN tun125 и mixed 127.0.0.1:2412,
selector → Remnawave, direct, route sniff/hijack-dns/private direct,
clash_api и cache_file. Они определяются template, не серверным инбаундом.

## Пример

Для Demo из [xray-base64.md](xray-base64.md) generated outbound:

```json
{
  "type": "vless",
  "tag": "Demo",
  "server": "vpn.example.com",
  "server_port": 443,
  "uuid": "11111111-1111-4111-8111-111111111111",
  "transport": {
    "type": "ws",
    "max_early_data": 2048,
    "early_data_header_name": "Sec-WebSocket-Protocol",
    "path": "/ws",
    "headers": {"Host": "cdn.example.com"}
  },
  "tls": {
    "enabled": true,
    "server_name": "cdn.example.com",
    "utls": {"enabled": true, "fingerprint": "chrome"},
    "alpn": ["h2", "http/1.1"]
  }
}
```

Для template `{"outbounds":[{"type":"selector","tag":"Select","outbounds":["old"]}]}`
полный результат — один object с outbounds=[selector(outbounds=['Demo']), outbound Demo].
Для Hysteria2 input udpHop.ports=`200-100,443,443-70000`, interval=10:
server_ports=["100:200","443:443","443:443"], hop_interval="10s".

## Python-перенос и проверки

Разделить build_base_outbound/build_hysteria2_outbound, transport/security/multiplex,
parse_positive_int/parse_port_ranges/parse_duration и render_selector_lists.
Mapper применять до списков selector/urltest. Исправление потери certificate pin или
unsupported transport — отдельное изменение поведения, не часть совместимого переноса.

Проверить:

1. VLESS none/custom encryption; vision только TCP с security; SS UOT versions 1/2.
2. XHTTP/KCP skip; TCP HTTP loss; HTTPUpgrade отдельный host и отсутствие ed-разбора.
3. WS Number('12x')/Number('')/float/Infinity; header Host variants и нестроковые values.
4. TLS ALPN trim с пустыми элементами, uppercase fingerprint, Reality empty publicKey/shortId.
5. Multiplex enabled=true vs truthy string; протоколы, partial parse, bool, brutal оба speed.
6. UOT подавляет multiplex до mapper; Hysteria2 multiplex вообще не строит.
7. Hysteria2 tls.enabled при none, pins, отсутствие utls; speed strings/units.
8. Port single/range/reversed/invalid/oversize/duplicates; duration 0/0s/decimal/suffix.
9. Obfs первый подходящий пароль, packetSize ignored, finalMask не копируется целиком.
10. Template before generated; selectors заменить, includeProxies=false сохранить;
    template proxies в tag lists, root remnawave оставить.
11. Mapper меняет tag/type до lists; per-host failure skip против render failure `''`.
