/**
 * Calcul HUOX — suivi d'usage anonyme (réception dans un Google Sheet).
 *
 * Ce script reçoit, de la part du backend (Render), une ligne par calcul
 * (compteurs et codes courts, voir backend/app/tracking.py) et l'ajoute
 * à l'onglet « Calculs » du Google Sheet.
 *
 * INSTALLATION (une seule fois)
 * -----------------------------
 * 1. Créer un Google Sheet (par exemple « Suivi Calcul HUOX »).
 * 2. Extensions → Apps Script. Remplacer le contenu de Code.gs par ce fichier.
 * 3. Roue crantée « Paramètres du projet » → Propriétés de script → Ajouter
 *    une propriété :  nom = SECRET   valeur = un mot de passe long et aléatoire
 *    (la même valeur sera mise dans la variable Render TRACKING_SECRET).
 * 4. Sélectionner la fonction « testLigne » en haut, cliquer sur Exécuter, accepter
 *    les autorisations demandées. Une ligne de test apparaît dans le Sheet
 *    (à supprimer ensuite).
 * 5. Déployer → Nouveau déploiement → type « Application Web » :
 *      Exécuter en tant que : Moi
 *      Qui a accès : Tout le monde
 *    Copier l'URL de l'application Web (elle se termine par /exec) :
 *    c'est la valeur de la variable Render TRACKING_URL.
 *
 * Après toute modification de ce script : Déployer → Gérer les déploiements →
 * crayon → Version « Nouvelle version » → Déployer (l'URL ne change pas).
 *
 * Sécurité : l'URL /exec est accessible à tous, mais toute requête dont le champ
 * « secret » ne correspond pas à la propriété SECRET est ignorée.
 */

var SHEET_NAME = 'Calculs';
var TIMEZONE   = 'Europe/Paris';
var HEADERS = [
  'Date et heure (Paris)', 'Résultat', 'Durée (s)', 'Matériaux', 'RC',
  'Cas de charge', 'Éléments', 'Erreur', 'Avertissements'
];

function doPost(e) {
  try {
    var secret = PropertiesService.getScriptProperties().getProperty('SECRET');
    var d = JSON.parse(e.postData.contents);
    if (!secret || d.secret !== secret) {
      return _reponse('refuse');
    }
    var lock = LockService.getScriptLock();
    lock.waitLock(15000);
    try {
      _ajouterLigne(d);
    } finally {
      lock.releaseLock();
    }
    return _reponse('ok');
  } catch (err) {
    return _reponse('erreur');
  }
}

// Ouvrir l'URL /exec dans un navigateur permet de vérifier que le déploiement répond.
function doGet() {
  return _reponse('Calcul HUOX — suivi actif');
}

function _ajouterLigne(d) {
  var quand = Utilities.formatDate(new Date(d.t), TIMEZONE, 'yyyy-MM-dd HH:mm:ss');
  _feuille().appendRow([
    quand,
    d.ok ? 'succès' : 'échec',
    _v(d.duree_s),
    _v(d.materiaux),
    _v(d.rc),
    _v(d.cdc),
    _v(d.elements),
    _v(d.erreur),
    _v(d.avertissements)
  ]);
}

function _feuille() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);
  if (sh.getLastRow() === 0) {
    sh.appendRow(HEADERS);
    sh.setFrozenRows(1);
    sh.getRange(1, 1, 1, HEADERS.length).setFontWeight('bold');
  }
  return sh;
}

function _v(x) {
  return (x === null || x === undefined) ? '' : x;
}

function _reponse(texte) {
  return ContentService.createTextOutput(texte);
}

// À exécuter une fois à la main (étape 4) pour autoriser le script et vérifier l'écriture.
function testLigne() {
  _ajouterLigne({
    t: new Date().toISOString(), ok: true, duree_s: 0.1, materiaux: 1, rc: 1,
    cdc: 1, elements: 1, erreur: '', avertissements: 'TEST'
  });
}
