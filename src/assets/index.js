// All images are imported here so the bundler fingerprints them and a missing
// file fails the build instead of showing a broken image.
import brand from "./icons/brand.svg";
import brandAuth from "./icons/brand-auth.svg";
import navDashboard from "./icons/nav-dashboard.svg";
import navReports from "./icons/nav-reports.svg";
import navAlerts from "./icons/nav-alerts.svg";
import navSettings from "./icons/nav-settings.svg";
import logout from "./icons/logout.svg";
import plant from "./icons/plant.svg";
import chevronSm from "./icons/chevron-sm.svg";
import chevronLg from "./icons/chevron-lg.svg";
import plantSelect from "./icons/plant-select.svg";
import statusOn from "./icons/status-on.svg";
import statusOff from "./icons/status-off.svg";
import fieldUser from "./icons/field-user.svg";
import fieldMail from "./icons/field-mail.svg";
import fieldPhone from "./icons/field-phone.svg";
import fieldLock from "./icons/field-lock.svg";
import contactAddress from "./icons/contact-address.svg";
import contactPhone from "./icons/contact-phone.svg";
import contactMail from "./icons/contact-mail.svg";
import cardElectrical from "./icons/card-electrical.svg";
import cardEnergy from "./icons/card-energy.svg";
import cardPerformance from "./icons/card-performance.svg";
import cardMotor from "./icons/card-motor.svg";

import heroMill from "./images/hero-mill.svg";
import authMill from "./images/auth-mill.svg";
import machineBanner from "./images/machine-banner.svg";
import loadGauge from "./images/load-gauge.svg";
import alertMachine from "./images/alert-machine.svg";
import settingsPassword from "./images/settings-password.svg";
import settingsPhone from "./images/settings-phone.svg";
import settingsLogout from "./images/settings-logout.svg";
import shellerCard from "./images/sheller-card.svg";
import shellerRail from "./images/sheller-rail.svg";
import whitener from "./images/whitener.svg";
import polisherCard from "./images/polisher-card.svg";
import polisherRail from "./images/polisher-rail.svg";
import sortex from "./images/sortex.svg";

export const icons = {
  brand,
  brandAuth,
  navDashboard,
  navReports,
  navAlerts,
  navSettings,
  logout,
  plant,
  chevronSm,
  chevronLg,
  plantSelect,
  statusOn,
  statusOff,
  fieldUser,
  fieldMail,
  fieldPhone,
  fieldLock,
  contactAddress,
  contactPhone,
  contactMail,
  cardElectrical,
  cardEnergy,
  cardPerformance,
  cardMotor,
};

export const images = {
  heroMill,
  authMill,
  machineBanner,
  loadGauge,
  alertMachine,
  settingsPassword,
  settingsPhone,
  settingsLogout,
};

/** Picture for each machine `type` the API can return. */
const machineArt = {
  sheller: { card: shellerCard, rail: shellerRail },
  whitener: { card: whitener, rail: whitener },
  polisher: { card: polisherCard, rail: polisherRail },
  sortex: { card: sortex, rail: sortex },
};
export const machineImage = (type, variant = "card") =>
  (machineArt[type] ?? machineArt.sheller)[variant];
