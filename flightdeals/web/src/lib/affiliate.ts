/**
 * Affiliate deep links. Every outbound booking click goes through /go/:dealId
 * which logs the click then 302s to one of these.
 */

const TP_MARKER = process.env.TRAVELPAYOUTS_MARKER;

/** Decorate a stored deep link with our marker, or build a search fallback. */
export function bookingUrl(deal: {
  deep_link: string | null;
  origin: string;
  destination: string;
  depart_date: string;
  return_date: string | null;
}): string {
  if (deal.deep_link) {
    if (TP_MARKER && deal.deep_link.includes("aviasales") && !deal.deep_link.includes("marker=")) {
      const sep = deal.deep_link.includes("?") ? "&" : "?";
      return `${deal.deep_link}${sep}marker=${TP_MARKER}`;
    }
    return deal.deep_link;
  }
  // Fallback: Aviasales search URL (DDMM format), still affiliate-tagged.
  const ddmm = (iso: string) => `${iso.slice(8, 10)}${iso.slice(5, 7)}`;
  const out = ddmm(deal.depart_date);
  const back = deal.return_date ? ddmm(deal.return_date) : "";
  const search = `${deal.origin}${out}${deal.destination}${back}1`;
  const marker = TP_MARKER ? `?marker=${TP_MARKER}` : "";
  return `https://www.aviasales.com/search/${search}${marker}`;
}
