# vendor

Lokaal meegeleverde afhankelijkheden, zodat de HUD geen CDN nodig heeft tijdens
runtime (en offline blijft werken).

- `three.module.min.js` + `three.core.min.js` — Three.js r180, MIT-licentie.
  Opgehaald met `npm pack three@0.180.0`. Zie `three.LICENSE`.

Bijwerken: `npm pack three@<versie>`, uitpakken en beide buildbestanden
vervangen. De importmap in `index.html` wijst naar `three.module.min.js`.
