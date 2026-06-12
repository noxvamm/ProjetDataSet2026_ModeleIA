#ifndef PAGEACCUEIL_H
#define PAGEACCUEIL_H

#include <QWidget>
#include "sessiondata.h"

namespace Ui {
class pageAccueil;
}

class pageAccueil : public QWidget
{
    Q_OBJECT

public:
    explicit pageAccueil(SessionData *data, QWidget *parent = nullptr);
    ~pageAccueil();

signals:
    void testCNCSelected();
    void testMoteurSelected();

private:
    Ui::pageAccueil *ui;
    SessionData *m_data;
};

#endif // PAGEACCUEIL_H
