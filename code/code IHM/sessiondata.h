#ifndef SESSIONDATA_H
#define SESSIONDATA_H

#include <QString>

struct SessionData {
    // Page 1
    double dureeEnregistrement = 1.0;
    double frequenceEchantillonnage = 44100.0;

    // Test Moteur
    QString frein;
    double frequenceEchantillonnageSon = 44100.0;
    double frequenceEchantillonnageVibration = 44100.0;
    int niveauPuissance = 0;




    // Page 2
    QString matiere;
    QString vitesseCoupe;
    QString vitesseAvance;
    QString typeOutil;
    QString pareurOutil;
    QString profondeurPasse;

    // Page 3
    QString noMesure;
    QString niveauUsure;
    QString totalMesures;

    QString toCSVHeader() const {
        return "duree,frequence_son,frequence_vibration,matiere,vitesse_coupe,"
               "vitesse_avance,type_outil,pareur_outil,"
               "niveau_usure";
    }

    QString toDataLine() const {
        return QString("%1,%2,%3,%4,%5,%6,%7,%8,%9")
            .arg(dureeEnregistrement)
            .arg(frequenceEchantillonnageSon)
            .arg(frequenceEchantillonnageVibration)
            .arg(matiere)
            .arg(vitesseCoupe)
            .arg(vitesseAvance)
            .arg(typeOutil)
            .arg(pareurOutil)
            .arg(niveauUsure);
    }

    QString toCSVHeaderMoteur() const {
        return "frein,duree,frequence_son,frequence_vibration,puissance";
    }

    QString toDataLineMoteur() const {
        return QString("%1,%2,%3,%4,%5")
            .arg(frein)
            .arg(dureeEnregistrement)
            .arg(frequenceEchantillonnageSon)
            .arg(frequenceEchantillonnageVibration)
            .arg(niveauPuissance);
    }
};

#endif // SESSIONDATA_H
