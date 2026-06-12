#ifndef CONFIGURATIONENREGISTREMENT_H
#define CONFIGURATIONENREGISTREMENT_H

#include <QMainWindow>
#include "sessiondata.h"

class contexteUsinage;
class niveauUsure;
class lancementEnregistrement;
class pageAccueil;
class configurationMoteur;
class supervisionMoteur;

QT_BEGIN_NAMESPACE
namespace Ui {
class configurationEnregistrement;
}
QT_END_NAMESPACE

class configurationEnregistrement : public QMainWindow
{
    Q_OBJECT

public:
    explicit configurationEnregistrement(QWidget *parent = nullptr);
    ~configurationEnregistrement();

private:
    Ui::configurationEnregistrement *ui;
    SessionData *m_data;
    contexteUsinage *m_page2;
    niveauUsure *m_page3;
    lancementEnregistrement *m_page4;
    pageAccueil *m_pageAccueil;
    configurationMoteur *m_configMoteur;
    supervisionMoteur *m_supervisionMoteur;
};

#endif // CONFIGURATIONENREGISTREMENT_H
