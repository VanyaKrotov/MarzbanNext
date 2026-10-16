# CLASH: обычный Clash YAML

Источник: Remnawave backend **3.4.5**, коммит `010b365ab1fabea01192b5e6ade4e98e66ee1dbd`.
Предобработка: [common.md](common.md). Расширенный генератор: [mihomo.md](mihomo.md).

## Исходники и интерфейс

Файл: [src/modules/subscription-template/generators/clash.generator.service.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription-template/generators/clash.generator.service.ts).

| Методы | Строки | Назначение |
| --- | --- | --- |
| generateConfig | 58–83 | Отбор и список proxies |
| buildProxyNode / applyProtocolFields | 85–129 | База proxy и credentials |
| applySecurityFields / resolveFingerprint | 131–167 | TLS/fingerprint |
| resolveClashNetwork / buildNetworkOpts | 169–204 | Network |
| buildWsOpts / buildTcpOpts / buildGrpcOpts | 206–262 | Transport-specific options |
| renderConfig / resolveGroupRemarks | 266–334 | Клиентский шаблон и группы |

Вход: hosts, overrideTemplateName. Выход: один YAML-документ, Content-Type text/yaml.
Никакого isExtendedClient/isStash здесь нет. Загружается template type CLASH.

## Поддержка и фильтры

```ts
const UNSUPPORTED_TRANSPORTS = new Set(['hysteria', 'kcp', 'xhttp']);
const UNSUPPORTED_PROTOCOLS = new Set(['hysteria', 'vless']);
```

Отбрасываются exclusions containing CLASH, указанные transport/protocol.
Фактически credentials builder поддерживает только Trojan и Shadowsocks.
VMess ветки нет, несмотря на возможные поля alterId в TypeScript-интерфейсе.
VLESS dummy fallback тоже исключается: custom remarks могут исчезнуть из Clash подписки.

isHidden/isDisabled внутри генератора не проверяются: в публичном CLASH pipeline
они исключены SQL. Прямой вызов допускает такие hosts. Порядок proxies — порядок входа.
Ошибки общего generateConfig/renderConfig → лог и `''`; per-host recovery отсутствует.
Пустой набор hosts всё равно проходит renderConfig и возвращает шаблон с массивами.

## Proxy builder

```ts
const node: ProxyNode = {
    name: host.finalRemark,
    type: this.resolveClashType(host.protocol),
    server: host.address,
    port: host.port,
    network: this.resolveClashNetwork(host),
    udp: true,
};
```

Trojan добавляет password. Shadowsocks → type=ss, password и cipher=method.
UOT/version SS игнорируются в отличие от Mihomo и sing-box. Не добавляются
ip-version, smux/mux, serverDescription, packet-encoding и host mapper.

Network: tcp с header.type=http → http; httpupgrade → ws; иначе transport.
Затем protocol fields → security → network options, при непустом options записать
`node[network + '-opts']`, затем client-fingerprint.

## Security

Для TLS:

- tls=true.
- Trojan: sni=serverName ?? ''; SS: servername=serverName ?? ''.
- Truthy alpn → split(',') без trim.
- Truthy pinnedPeerCertSha256 → skip-cert-verify=true **в том числе для SS**.
  Сам сертификатный pin не выводится.

Reality и none в security switch дополнительных полей не добавляют. Reality не
исключается заранее, поэтому теоретически Trojan/SS+Reality могут породить proxy
без reality-opts/tls; перенос не должен молча добавлять поддержку Reality.
verifyPeerCertByName, ECH, cipherSuites и session resumption не выводятся.

client-fingerprint всегда присутствует: lowercase исходной строки, первое substring
совпадение в FINGERPRINTS, иначе chrome. Порядок списка указан в [common.md](common.md)
и [mihomo.md](mihomo.md). При security=none или неуказанном fingerprint → chrome.

## Transport

| Transport | Результат |
| --- | --- |
| ws | network=ws, ws-opts из path/host |
| httpupgrade | network=ws, ws-opts + v2ray-http-upgrade=true, v2ray-http-upgrade-fast-open=true |
| tcp | network=tcp или http; options={} всегда, tcp/http-opts отсутствуют |
| grpc | network=grpc, grpc-opts.grpc-service-name=serviceName ?? '' |

TCP camouflage headers/path не копируются. gRPC authority/multiMode игнорируются.
WS/httpupgrade raw transportOptions.headers полностью игнорируются: builder принимает
только path, host, isHttpUpgrade. Это отличается от Mihomo.

Разбор `?ed=` точно такой же, как в Mihomo:

1. rawPath ?? ''. При точном `?ed=` path разбить, взять первую часть как новый path.
2. В следующей части до `/` выполнить JS parseInt без явного radix.
3. Число, включая 0/отрицательное → max-early-data; NaN → поле отсутствует.
4. early-data-header-name=Sec-WebSocket-Protocol добавляется при наличии `?ed=` даже при NaN.
5. Непустой path добавить, headers всегда `{Host:host}` либо `{}`.

Из-за headers={} WS options всегда непустые. `/ws?ed=12x` → path=/ws,
max-early-data=12. Нельзя переносить этот разбор через Python int('12x') или брать
из sing-box, где используется Number и строка считается невалидной.

## Шаблон и группы

Загрузка CLASH template происходит в renderConfig **после** генерации proxies.
Выбор имени/Default, YAML merge schema и cache описаны в [common.md](common.md).
Результат:

```text
root = shallow copy template
root.proxies = array(template.proxies) + generated proxies
root.proxy-groups = render каждой группы из array(template.proxy-groups)
```

Если исходные proxies/proxy-groups не arrays, считаются пустыми. Прочие root поля
сохраняются. Root remnawave **не удаляется** (в отличие от Mihomo).
proxy-providers сохраняются из шаблона без обработки payload/include-proxies.
DNS, rules и локальные порты не вычисляются по hosts; используются из шаблона.
data.rules создан, но в результирующий конфиг не внедряется.

В каждой группе служебный remnawave убирается; selection priority:
include-proxies===false → не добавлять generated names;
иначе select-random-proxy===true → одно случайное имя;
иначе shuffle-proxies-order===true → все имена shuffle;
иначе все имена по порядку. Original group.proxies (только array) всегда остаётся
перед generated names, даже при include-proxies=false. Не выполняются dedup и validation.
При нулевом списке random возвращает []. Группа select/url-test обрабатывается одинаково:
тип группы не влияет на включение names.

Сериализация js-yaml.dump(finalConfig). Комментарии, anchors и форматирование
исходного текста могут измениться. Отсутствие unsupported nodes не считается ошибкой:
даже VLESS-only subscription может вернуть YAML с пустыми proxies и сохранённой группой.

## Пример

Для resolved host Demo из [xray-base64.md](xray-base64.md), но protocol=trojan и
protocolOptions={password:'secret'}, generated proxy:

```yaml
name: Demo
type: trojan
server: vpn.example.com
port: 443
network: ws
udp: true
password: secret
tls: true
sni: cdn.example.com
alpn: [h2, http/1.1]
ws-opts:
  path: /ws
  headers:
    Host: cdn.example.com
  max-early-data: 2048
  early-data-header-name: Sec-WebSocket-Protocol
client-fingerprint: chrome
```

Минимальный иллюстративный template:

```yaml
proxies: []
proxy-groups:
  - name: Select
    type: select
    proxies: [DIRECT]
rules:
  - MATCH,Select
```

После render: proxies содержит proxy Demo, группа proxies=[DIRECT, Demo], rules остаются.
Default CLASH template дополнительно задаёт mixed-port=7890, socks-port=7891,
redir-port=7892, mode=global, DNS fake-ip и группу → Remnawave.

## Python-перенос и проверки

Предлагается общий renderer YAML-групп с Mihomo, но отдельный Clash proxy builder.
Передавать явно флаги preserve_root_remnawave=true, process_providers=false,
apply_mapper=false и отсутствие raw WS headers; не считать обычный Clash alias Mihomo.

Проверить:

1. Trojan/SS допускаются, VLESS/Hysteria/VMess и KCP/XHTTP/hysteria transport пропускаются.
2. SS2022 password приходит из resolver, UOT не записывается.
3. TLS pin включает skip-cert-verify для SS; Reality не создаёт reality-opts.
4. ALPN с пробелами без trim; uppercase fingerprints; security=none → chrome.
5. WS ed='2048','12x','',0,negative,hex; path split при повторном ?ed=.
6. WS raw headers игнорируются; HTTPUpgrade два flags; gRPC serviceName=null.
7. TCP HTTP network=http, request не переносится.
8. groups include/random/shuffle priority, original names и duplicates.
9. Root remnawave и providers сохраняются; group.remnawave удаляется.
10. Прямой hidden/disabled host не фильтруется; empty proxies при VLESS dummy fallback.
11. Отсутствующий template, invalid header runtime types и YAML dump error дают `''`.
