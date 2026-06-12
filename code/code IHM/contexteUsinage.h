#ifndef CONTEXTEUSINAGE_H
#define CONTEXTEUSINAGE_H

#include <QWidget>
#include "sessiondata.h"

namespace Ui {
class contexteUsinage;
}

class contexteUsinage : public QWidget
{
    Q_OBJECT

public:
    explicit contexteUsinage(SessionData *data, QWidget *parent = nullptr);
    ~contexteUsinage();

signals:
    void validationDemandee();
    void retourDemande();

private:
    Ui::contexteUsinage *ui;
    SessionData *m_data;
};

#endif // CONTEXTEUSINAGE_H
