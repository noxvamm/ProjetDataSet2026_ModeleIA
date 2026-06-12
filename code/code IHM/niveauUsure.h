#ifndef NIVEAUUSURE_H
#define NIVEAUUSURE_H

#include <QWidget>
#include "sessiondata.h"

namespace Ui {
class niveauUsure;
}

class niveauUsure : public QWidget
{
    Q_OBJECT

public:
    explicit niveauUsure(SessionData *data, QWidget *parent = nullptr);
    ~niveauUsure();

signals:
    void validationDemandee();
    void retourDemande();

private:
    Ui::niveauUsure *ui;
    SessionData *m_data;
};

#endif // NIVEAUUSURE_H
