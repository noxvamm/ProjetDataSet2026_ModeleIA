#ifndef CONFIGURATIONMOTEUR_H
#define CONFIGURATIONMOTEUR_H

#include <QWidget>
#include "sessiondata.h"

namespace Ui {
class configurationMoteur;
}

class configurationMoteur : public QWidget
{
    Q_OBJECT

public:
    explicit configurationMoteur(SessionData *data, QWidget *parent = nullptr);
    ~configurationMoteur();

signals:
    void validationDemandee();
    void retourDemande();

private:
    Ui::configurationMoteur *ui;
    SessionData *m_data;
};

#endif // CONFIGURATIONMOTEUR_H
