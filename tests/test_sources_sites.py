from collecte.sources_sites import decouvrir_liens_annonces, decouvrir_liens_sitemap

HTML_INDEX_STANDARD = """
<html><body>
<a href="/en/property/1234/beautiful-villa.html">Villa</a>
<a href="/en/property/5678/terrain-a-vendre.html">Terrain</a>
<a href="/contact">Contact</a>
<a href="https://autresite.mu/property/999/">Site externe</a>
</body></html>
"""

SITEMAP_URLS_ABSOLUES = """
<urlset xmlns="https://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://exemple.mu/en/property/1234/villa-a-vendre.html</loc></url>
  <url><loc>https://exemple.mu/en/property/5678/terrain.html</loc></url>
  <url><loc>https://exemple.mu/contact</loc></url>
</urlset>
"""

SITEMAP_URLS_RELATIVES = """
<urlset xmlns="https://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>en/property/1234/villa-a-vendre.html</loc></url>
</urlset>
"""

SITEMAP_INDEX = """
<sitemapindex xmlns="https://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://exemple.mu/post-sitemap.xml</loc></sitemap>
  <sitemap><loc>https://exemple.mu/property-sitemap1.xml</loc></sitemap>
</sitemapindex>
"""


class TestDecouvrirLiensAnnonces:
    def test_ne_retient_que_le_meme_domaine(self):
        liens = decouvrir_liens_annonces(HTML_INDEX_STANDARD, "https://exemple.mu/")
        assert all("autresite.mu" not in l for l in liens)

    def test_matche_le_motif_par_defaut(self):
        liens = decouvrir_liens_annonces(HTML_INDEX_STANDARD, "https://exemple.mu/")
        assert any("1234" in l for l in liens)
        assert any("5678" in l for l in liens)

    def test_motif_personnalise(self):
        html = '<a href="/index.php?action=detail&nbien=42">Fiche</a><a href="/contact">Contact</a>'
        liens = decouvrir_liens_annonces(html, "https://exemple.mu/", motif_regex=r"nbien=\d+")
        assert len(liens) == 1
        assert "nbien=42" in liens[0]


class TestDecouvrirLiensSitemap:
    def test_extrait_et_filtre_les_loc(self):
        liens, sous_sitemaps = decouvrir_liens_sitemap(
            SITEMAP_URLS_ABSOLUES, "https://exemple.mu/sitemap.xml"
        )
        assert len(liens) == 2
        assert sous_sitemaps == []

    def test_resout_les_loc_relatives_en_absolues(self):
        liens, _ = decouvrir_liens_sitemap(SITEMAP_URLS_RELATIVES, "https://exemple.mu/sitemap.xml")
        assert liens == ["https://exemple.mu/en/property/1234/villa-a-vendre.html"]

    def test_separe_les_sous_sitemaps(self):
        liens, sous_sitemaps = decouvrir_liens_sitemap(SITEMAP_INDEX, "https://exemple.mu/sitemap.xml")
        assert liens == []
        assert sous_sitemaps == [
            "https://exemple.mu/post-sitemap.xml",
            "https://exemple.mu/property-sitemap1.xml",
        ]

    def test_motif_personnalise_pour_slugs_sans_chiffre(self):
        html = """
        <urlset>
          <url><loc>https://seeff.mu/property/</loc></url>
          <url><loc>https://seeff.mu/property/villa-exceptionnelle-a-grand-baie/</loc></url>
        </urlset>
        """
        liens, _ = decouvrir_liens_sitemap(
            html, "https://seeff.mu/sitemap.xml", motif_regex=r"/property/[a-z0-9-]{8,}"
        )
        assert liens == ["https://seeff.mu/property/villa-exceptionnelle-a-grand-baie/"]
