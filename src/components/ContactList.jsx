import { icons } from "../assets";
import { config } from "../config";
import { AssetIcon } from "./Icon";

export function ContactList() {
  const rows = [
    [icons.contactAddress, config.company.address],
    [icons.contactPhone, config.company.phone],
    [icons.contactMail, config.company.email],
  ].filter(([, text]) => text);
  if (!rows.length) return null;
  return (
    <ul>
      {rows.map(([icon, text]) => (
        <li key={text}>
          <AssetIcon src={icon} size={20} />
          {text}
        </li>
      ))}
    </ul>
  );
}
