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

## Try it with a simulated gateway (AWS free plan, no hardware)

This proves the whole path (gateway → AWS IoT Core → your backend → dashboard) before you buy a gateway.
Your laptop can run the backend without a public address: the **bridge** below subscribes to AWS from your
machine, so no IoT Rule or tunnel is needed.

```
tools/mqtt_gateway_sim.py ──MQTT/TLS──▶ AWS IoT Core ◀──MQTT/TLS── manage.py iot_bridge ──▶ your backend
```

**1. Find your endpoint.** AWS Console → IoT Core → *Settings* → *Device data endpoint*
(`xxxxxxxx-ats.iot.<region>.amazonaws.com`). Use the same region everywhere.

**2. Create the two policies** (IoT Core → Security → Policies → Create). Replace `REGION` and `ACCOUNT`
(12 digits, top right menu).

`nsms-gateway-policy` is the policy shown in section 2 above.

`nsms-bridge-policy`:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Action": "iot:Connect",
      "Resource": "arn:aws:iot:REGION:ACCOUNT:client/nsms-bridge" },
    { "Effect": "Allow", "Action": "iot:Subscribe",
      "Resource": "arn:aws:iot:REGION:ACCOUNT:topicfilter/mill/+/readings" },
    { "Effect": "Allow", "Action": "iot:Receive",
      "Resource": "arn:aws:iot:REGION:ACCOUNT:topic/mill/*/readings" }
  ]
}
```
Note the difference: `Subscribe` names the filter exactly as the bridge subscribes (`mill/+/readings`), but
`Receive` is checked against each real topic, where `+` is **not** a wildcard in a policy. Use `*` there. With
`+` the bridge connects normally and subscribes, but AWS silently delivers nothing.

**3. Create the simulated gateway.** IoT Core → Manage → All devices → Things → *Create things* → one thing,
named **`SIM-GW-0001`** (the name is the serial), no shadow, *Auto-generate a new certificate*, attach
`nsms-gateway-policy`. Download the *device certificate* and *private key* (the page is your only chance),
and the *Amazon root CA 1*. Rename them `SIM-GW-0001.cert.pem`, `SIM-GW-0001.private.key`,
`AmazonRootCA1.pem`.

**4. Create the bridge certificate.** Security → Certificates → *Add certificate* → *Create certificate*
(auto-generated), activate it, attach `nsms-bridge-policy`, download the certificate and key as
`bridge.cert.pem` and `bridge.private.key`. It does not need a Thing.

Keep all these files out of git (the repository already ignores `*.pem` and `*.private.key`).

**5. Start the backend and the bridge** (in `backend/`, with your virtualenv active):
```bash
pip install -r requirements.txt
python manage.py migrate
daphne -b 127.0.0.1 -p 8000 config.asgi:application          # terminal 1
python manage.py iot_bridge --endpoint <your endpoint> \
    --cert bridge.cert.pem --key bridge.private.key --ca AmazonRootCA1.pem   # terminal 2
```
It prints `Connected … listening on mill/+/readings`.

**6. Run the simulated gateway** (terminal 3):
```bash
pip install paho-mqtt
python tools/mqtt_gateway_sim.py --endpoint <your endpoint> --serial SIM-GW-0001 \
    --cert SIM-GW-0001.cert.pem --key SIM-GW-0001.private.key --ca AmazonRootCA1.pem --interval 10
```
It prints `published #1 …`. To see the messages in AWS itself, open IoT Core → *MQTT test client* and
subscribe to `mill/#`.

**7. Approve it in the app.** The bridge first prints `refused: This gateway is waiting for the
administrator to verify it`. Sign in as admin → Gateways → **Verify** `SIM-GW-0001` → **Assign** it to an
approved plant owner → **Connect**. The next messages print `stored 4, rejected 0`. Sign in as that owner:
four machines (`Meter 1`…`Meter 4`) show live values. Data sent before verification is not kept.

**Costs.** IoT Core bills per message, and each publish plus its delivery to the bridge counts. At one
message every 5 s that is about a million messages a month, so use `--interval 30` for long runs and stop
the simulator when you are not testing. Check the current free-tier limits on the AWS IoT Core pricing page.

**To use the IoT Rule instead of the bridge** (needs a public HTTPS backend, see
[DEPLOY.md](DEPLOY.md)), follow sections 1 and 2 above. Using both at once is
unnecessary (duplicate samples are ignored, so nothing is double counted), so choose one.
The bridge only sees messages published while it is running, so keep it supervised (the Docker setup restarts it).

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
