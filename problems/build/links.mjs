// Shared by resolve-links.mjs and build-nanopubs.mjs: how a reference becomes a URL.
export const doiUrl = doi => `https://doi.org/${String(doi).trim().replace(/^https?:\/\/(dx\.)?doi\.org\//, "")}`;
export const linkOf = ref => (ref.doi ? doiUrl(ref.doi) : ref.url ? String(ref.url).trim() : null);
