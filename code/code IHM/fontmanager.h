#ifndef FONTMANAGER_H
#define FONTMANAGER_H

#include <QFont>

class fontmanager
{
public:
    static QFont globalFont() {
        return QFont("Arial", 10);   // Police globale
    }

    static QFont titleFont() {
        QFont f("Arial", 20);        // Taille du titre
        f.setBold(true);
        return f;
    }

    static QFont buttonFont() {
        QFont f("Arial", 12);        // Taille du bouton Valider
        f.setBold(true);
        return f;
    }

    static QFont backFont() {
        QFont f("Arial", 12);        // Taille du bouton Retour
        f.setBold(true);
        return f;
    }
};

#endif // FONTMANAGER_H
