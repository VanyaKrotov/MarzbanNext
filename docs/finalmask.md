# Final mask в настройках хоста

Поле задаёт `overrides.stream.final_mask`. Генератор Xray переносит объект в
`outbounds[].streamSettings.finalmask`. Clash, sing-box, URI/Base64 и Outline
не получают этот объект. Это настройки клиентского подключения: сервер и версия
клиентского ядра должны поддерживать выбранные маски.

В диалоге «Настроить» Monaco подсказывает поля выбранного `type`, описывает единицы
измерения и проверяет типы, обязательные поля, диапазоны, кодировки и сочетания
источников данных. API проверяет тот же контракт; дополнительные взаимозависимости
(например, последний элемент `fragment.lengths`) проверяются на сервере.
Неизвестные ключи и маски другой транспортной группы отклоняются.

Каталог сверён с [загрузчиками Xray](https://github.com/XTLS/Xray-core/blob/1b1647cd9ddf0abc34b981d4611fc03bcac1ca74/infra/conf/transport_finalmask.go),
ревизия `1b1647cd9ddf0abc34b981d4611fc03bcac1ca74`.
Общее описание: [документация Xray](https://xtls.github.io/en/config/transports/finalmask.html).
Наличие типа в схеме панели не добавляет его поддержку в старые клиентские ядра.
Lua-скрипты, сертификаты, подписи профилей, файлы и сетевое взаимодействие
проверяет клиентское ядро. Панель не исполняет скрипты и не читает клиентские файлы.

## Структура

```json
{
  "tcp": [
    {
      "type": "fragment",
      "settings": {
        "packets": "tlshello",
        "lengths": ["100-200"],
        "delays": ["10-20"]
      }
    }
  ],
  "udp": [
    { "type": "salamander", "settings": { "password": "shared-secret" } }
  ],
  "quicParams": { "congestion": "bbr" }
}
```

Все три поля необязательны. В маске обязателен `type`; для `fragment`, `xmc`,
`realm` и `udphop` нужен также заполненный `settings`. Порядок масок — от внутренней
к внешней: первый элемент ближе к исходным данным, последний — к сети.
`tcp: []`, `udp: []` и `{}` допустимы. Значения по умолчанию в JSON не дописываются.

Числовой диапазон задаётся целым числом, числовой строкой или строкой `A-B`:
`100`, `"100"`, `"100-200"`. Для обычных диапазонов Xray допускает обратные границы.
Пустая строка означает ноль. Длины, задержки и счётчики проверяются как
неотрицательные целые; boolean вместо числа запрещён.
Сохранённые `length`/`delay`, имена Sudoku с подчёркиванием и прежний
`quicParams.udpHop` поддерживаются без переписывания JSON.

## Каталог масок

| `type` | Где | Поля `settings` и назначение |
| --- | --- | --- |
| `filter` | TCP, UDP | `blockedSourceIPs`, `allowedSourceIPs`: списки IP/CIDR/geoip. Фильтр работает на входящей стороне; в клиентском outbound эффекта нет |
| `header-custom` | TCP, UDP | Произвольные заголовки, случайные байты, захват и повтор значений, выражения. Структуры TCP и UDP различаются; см. ниже |
| `fragment` | TCP | `packets`: `tlshello`, номера пакетов `1-3` или `""` для всех; `lengths`: диапазоны длины в байтах; `delays`: задержки в мс; `maxSplit`: число разбиений, `0` без ограничения. `length`/`delay` используются, если соответствующий массив пуст или отсутствует. Последняя длина должна быть положительной |
| `sudoku` | TCP, UDP | `password`; `ascii`: `prefer_entropy`/`entropy`, `prefer_ascii`/`ascii` или `""`; `customTable`, `customTables`: одна или несколько раскладок; `paddingMin`, `paddingMax`: вероятность заполнения в процентах. Xray ограничивает проценты до 100 и поднимает максимум до минимума. Раскладка содержит ровно 2 `x`, 2 `p` и 4 `v`, например `xpxpvvvv`. Сохранены `custom_table`, `custom_tables`, `padding_min`, `padding_max` |
| `xmc` | TCP | `hostname`: имя в Minecraft handshake; обязательные `password` и непустой `profiles`. В каждом профиле обязательны `username` (3–16 латинских букв, цифр, `_`), `uuid`, `texturesValue`, `texturesSignature`. Требуются настоящие подписанные данные профиля |
| `mkcp-legacy` | UDP | `header`: `dns`, `dtls`, `srtp`, `utp`, `wechat`, `wireguard` или `""`. `value`: домен для DNS (default `www.baidu.com`) или пароль AES при пустом header. Пустые header/value выбирают прежнюю XOR-маскировку |
| `noise` | UDP | `reset`: повтор последовательности через N секунд, `0` отключает повтор; `noise`: список пакетов; `script`: Lua-скрипт. Непустые `noise` и `script` несовместимы |
| `salamander` | UDP | `password`; `packetSize`: `0` для обычного Salamander, положительный размер/диапазон до 2048 байт для Gecko |
| `xdns` | UDP | `domains`, `resolvers`, `extraPoll` (0–3). DNS-маскировка, обычно вместе с mKCP; определения ниже |
| `xicmp` | UDP | `dgram`: ICMP datagram вместо raw socket; `ips`: список IPv4/IPv6 без CIDR. Требуются подходящие права ОС и поддержка другой стороны |
| `realm` | UDP | Обязательные `url` (`realm://token@host/id` или `realm+http://token@host/id`) и непустой `stunServers` со значениями `host:port`; `tlsConfig`; `ipMode`: `dual`, `ipv4`, `ipv6` или `""`; `portMapping`: `enabled`, `timeout`, `lifetime` (секунды) |
| `udphop` | UDP | Обязательный `mode`: `intervallocal`, `intervalremote`, `perconnremote` или их список через запятую; `interval`: `0` (30 секунд) или диапазон от 5 секунд; `remoteIPs`: IP/CIDR; `remotePorts`: число или список портов/диапазонов. Локальный hopping зависит от транспорта, удалённый — от настройки маршрутизации портов сервера |

`settings` использует точные имена из таблицы. Пропуск параметра сохраняет поведение
ядра по умолчанию; `false`, `0`, пустая строка и пустой массив сохраняются явно.
Числа портов ограничены 0–65535; `0` и пустая строка задают пустой список.
В списках портов поддерживается `env:NAME`: значение берётся из окружения клиента.

## Произвольные заголовки

TCP принимает `clients`, `servers`, `errors`: массивы последовательностей
(`[[item, item], [item]]`). UDP принимает `mode` (`prefix` по умолчанию или
`standalone`), `client`, `server`: обычные массивы элементов (`[item, item]`).

| Поле элемента | Формат |
| --- | --- |
| `packet` | Массив байтов 0–255 или строка в выбранной кодировке |
| `type` | `array`/`""` — массив байтов или Base64-строка; `str` — текст; `hex` — пары hex-цифр без `0x`; `base64` — стандартный Base64 |
| `rand` | Количество случайных байтов; `0` отключает этот источник |
| `randRange` | Значения случайных байтов, диапазон 0–255 |
| `capture` | Имя для сохранения результата; латинская буква/`_`, затем буквы, цифры, `_` |
| `reuse` | Имя ранее сохранённого значения |
| `transform` | Выражение `{ "op": "...", "args": [...] }` |
| `delay` | Задержка перед отправкой элемента в мс; только TCP |

Активным источником может быть только один из `packet`, положительного `rand`,
непустого `reuse`, `transform`. Для непустого `capture` источник обязателен.
Сохранённый явный `packet: null` передаётся как `null`, а не удаляется.

Каждый аргумент выражения содержит ровно один источник: `bytes` (с необязательным
`type` кодировки), `u64` (0–2⁶⁴−1), `reuse`, `metadata` либо вложенный `transform`.
Метаданные: `local_port`, `remote_port`, `src_port_u16`, `dst_port_u16`,
`local_ip4_u32`, `remote_ip4_u32`, `src_ip4_u32`, `dst_ip4_u32`.
Доступность IP-метаданных зависит от адресов фактического соединения.

| `op` | Аргументы |
| --- | --- |
| `concat` | Один или несколько байтовых значений |
| `slice` | Байты, начальная позиция, конечная позиция |
| `xor16`, `xor32` | Байты, ключ |
| `be16`, `be32`, `le16`, `le32`, `le64` | Одно целое число для кодирования |
| `pad` | Байты, итоговая длина, непустые байты заполнения |
| `truncate` | Байты, итоговая длина |
| `add`, `sub`, `and`, `or`, `shl`, `shr` | Два целых числа |

Пример UDP-префикса с числом, полученным из метаданных:

```json
{
  "udp": [{
    "type": "header-custom",
    "settings": {
      "mode": "prefix",
      "client": [{
        "transform": {
          "op": "concat",
          "args": [
            { "type": "hex", "bytes": "0001" },
            { "transform": { "op": "be16", "args": [{ "metadata": "remote_port" }] } }
          ]
        }
      }]
    }
  }]
}
```

## Шумовые пакеты

Элемент `noise` принимает `rand` (диапазон длины), `randRange`, `type`, `packet`,
`delay` (мс). Случайная длина больше нуля и явный `packet` несовместимы.
Кроме обычных кодировок доступен `type: "exp"` со строкой из токенов:

| Токен | Результат |
| --- | --- |
| `<b 0001>` | Фиксированные hex-байты; допустим префикс `0x` |
| `<r 8-16>` | Случайные байты, длина 0–65535 |
| `<rc 8>` | Случайные ASCII-буквы |
| `<rd 8>` | Случайные цифры |
| `<t>` | Временная метка |
| `<c>` | Счётчик |
| `<n>` | Nonce |

Например: `"<b 0001><r 8-16><t><c><n>"`. У диапазонов внутри токенов
нижняя граница должна быть не больше верхней.

## XDNS и вложенные TLS-настройки

`domains[]`: `names` (домены), `lenLimit` (0/default 255, максимум 255),
`labelLimit` (0/default 63, максимум 63), `types` (1=A, 5=CNAME, 16=TXT, 28=AAAA),
`edns0` (0 или 512–4096).

`resolvers[]`: `addrs` (без схемы, `udp://`, `tcp://`, `https://`), `worker`
(0/default 32), `tlsConfig`, `quicConfig`. Для UDP/TCP без порта используется 53.
`quicConfig` имеет те же поля, что корневой `quicParams`.

В `tlsConfig` у XDNS и Realm описаны `certificates`, `serverName`, `alpn`,
`enableSessionResumption`, `disableSystemRoot`, `minVersion`, `maxVersion`,
`cipherSuites`, `fingerprint`, `rejectUnknownSni`, `curvePreferences`, `masterKeyLog`,
`pinnedPeerCertSha256`, `verifyPeerCertByName`, `echServerKeys`, `echConfigList`,
`echSockopt`, `useSystemCA`. Прежний `allowInsecure` сохранён и отмечен устаревшим.
ALPN и кривые принимают массив или строку через запятую; версии TLS — 1.0–1.3.
`echSockopt` использует ту же [подробную схему параметров сокета](socket-options.md),
что и `overrides.stream.sockopt`, включая Happy Eyeballs и `customSockopt`.

Элемент `certificates[]` содержит `certificateFile`/`certificate`, `keyFile`/`key`,
`usage` (`encipherment`, `verify`, `issue`), `ocspStapling` (секунды),
`oneTimeLoading`, `buildChain`. Inline PEM задаётся массивом строк; пути относятся
к устройству, запускающему клиентскую конфигурацию.

## QUIC

| Поля `quicParams` | Формат и ограничения |
| --- | --- |
| `congestion` | `reno`, `bbr`, `brutal`, `force-brutal`, `""`; force-brutal требует ненулевой `brutalUp` |
| `bbrProfile` | `conservative`, `standard`, `aggressive`, `""` |
| `brutalUp`, `brutalDown` | Строка бит/с: `"60 mbps"`, `"512 kbps"`, `"0"`. Xray использует множители 1024. Ненулевое значение — минимум 65536 байт/с, то есть 524288 бит/с |
| `brutalDisableLossCompensation` | Boolean, отключает компенсацию потерь |
| `initStreamReceiveWindow`, `maxStreamReceiveWindow`, `initConnectionReceiveWindow`, `maxConnectionReceiveWindow` | Байты; 0/default или минимум 16384 |
| `maxIdleTimeout` | 0/default или 4–120 секунд |
| `keepAlivePeriod` | 0 или 2–60 секунд |
| `maxIncomingStreams` | 0/default или минимум 8 |
| `debug` | Boolean, диагностические логи |
| `disablePathMTUDiscovery`, `disableChromeParrot`, `disableGSO`, `disableStatelessReset` | Boolean-переключатели QUIC |
| `udpHop` | Прежний объект `ports`, `interval` (минимум 5 секунд), отмечен устаревшим. Для новых ядер используется UDP-маска `udphop` |

Полная JSON Schema формируется из моделей `app/models/finalmask/` и публикуется
в `GET /api/hosts/capabilities`, `overrides_schema`. Тесты сверяют схему Monaco
с API, проверяют каталог, подсказки, ошибки, сохранение и выдачу конфигураций.
