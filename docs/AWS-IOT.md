# Connecting a gateway over MQTT (AWS IoT Core)

Most industrial gateways read the energy meters over Modbus (RS-485) and publish the values over
MQTT. This is how those values reach the backend.

```
Selec MFM384 meters ──RS-485/Modbus RTU──▶ gateway ──MQTT over TLS──▶ AWS IoT Core
   (one per machine)                       (one cert per gateway)          │ IoT Rule
                                                                           ▼  HTTPS POST + secret header
                                                       backend  POST /api/iot/ingest  → live dashboard, reports, alerts
```

The gateway never talks to the backend directly. AWS IoT Core checks each gateway's certificate and
policy; the rule then hands the message to the backend, which stores it exactly as it does for
`/api/ingest`.

## 1. Backend

Set a long random value for `IOT_RULE_SECRET` in the server environment and restart. Empty means the
endpoint is off. The backend must be reachable on a public HTTPS address with a valid certificate
(AWS will not call a self-signed one).

## 2. AWS IoT Core (once)

1. **Policy** (attach to every gateway certificate). It lets a gateway publish only under its own
   serial, so one gateway cannot pretend to be another:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       { "Effect": "Allow", "Action": "iot:Connect",
         "Resource": "arn:aws:iot:REGION:ACCOUNT:client/${iot:Connection.Thing.ThingName}" },
       { "Effect": "Allow", "Action": "iot:Publish",
         "Resource": "arn:aws:iot:REGION:ACCOUNT:topic/mill/${iot:Connection.Thing.ThingName}/readings" }
     ]
   }
   ```
2. **Rule destination** (HTTP): your `https://api.example.com/api/iot/ingest`. AWS sends one
   confirmation request to it. The backend logs the token (`AWS IoT destination confirmation token`);
   confirm it with `aws iot confirm-topic-rule-destination --confirmation-token <token>`.
3. **Rule**, SQL:
   ```sql
   SELECT topic(2) AS serial, readings FROM 'mill/+/readings'
   ```
   Action: HTTP to the destination above, with the header `X-IoT-Secret: <IOT_RULE_SECRET>` and
   `Content-Type: application/json`.

## 3. For each gateway

1. In IoT Core create a **Thing named exactly the gateway's serial number** (4 to 64 characters:
   letters, digits, `.`, `_`, `-`), create a certificate, attach the policy, and download the
   certificate, private key and the Amazon root CA.
2. In the gateway's MQTT settings enter the IoT Core endpoint (port 8883, TLS), the three files, and
   publish to the topic `mill/<serial>/readings` every few seconds.
3. Payload (JSON). Only `meterId` and `kw` are required; `ts` is epoch milliseconds and is filled in
   by the server if missing:
   ```json
   { "readings": [
       { "meterId": "1", "kw": 26.1, "pf": 0.93, "kva": 28.1, "kvar": 10.4,
         "current": 39.1, "voltage": 415, "frequency": 50.0, "kwh": 41250.4 },
       { "meterId": "2", "kw": 0, "pf": 0 }
   ] }
   ```
   `meterId` is the meter's Modbus slave address (a string). If the gateway's payload is fixed and
   looks different, tell me its shape: either the rule's SQL can reshape it, or the backend can accept it.
4. The first message makes the gateway appear in the Admin Portal as **unverified**. The admin verifies
   it, assigns it to a plant owner and connects it. Until then its data is not stored (the rule shows a 403).

## Selec MFM384 over Modbus RTU

The gateway polls each meter with **function code 4 (input registers)**, values are 32-bit floats (two
registers each, big-endian). Registers (offsets from a third-party register table; the address is
30000 + offset, check whether your gateway wants the 1-based or 0-based form against the meter manual
before trusting it):

| Value | Offset | JSON field |
|---|---|---|
| Total active power (kW) | 42 | `kw` |
| Total apparent power (kVA) | 44 | `kva` |
| Total reactive power (kvar) | 46 | `kvar` |
| Average current (A) | 22 | `current` |
| Average power factor | 54 | `pf` |
| Frequency (Hz) | 56 | `frequency` |

The energy counters (kWh, kvarh, kvah) are also on the meter, but I could not confirm their registers
from a reliable source: take them from the MFM384 manual. They are optional. Without `kwh` the backend
integrates `kw` over time, so reports still work.

Wire all meters on one RS-485 pair with a **different slave address each** (1, 2, 3, …), the same baud
rate and parity on every meter and on the gateway, and set each address as that machine's `meterId`.

## Choosing a gateway (budget about ₹30,000)

Check these before you buy; prices vary, so confirm them with the seller:

- RS-485 Modbus RTU **master** (polls the meters), with enough meters on one port (every MFM384 is a slave).
- **MQTT client with TLS and client certificates**, ideally a built-in "AWS IoT Core" option.
- A **custom JSON payload** (or a payload editor), so the output can match the format above.
- Store-and-forward: it buffers readings when the internet drops and sends them later (our `ts` field handles late data).
- 4G or Ethernet depending on the site, a DIN-rail mount, and an operating temperature that suits a mill.

I can check a specific model's manual against these once you shortlist two or three.
