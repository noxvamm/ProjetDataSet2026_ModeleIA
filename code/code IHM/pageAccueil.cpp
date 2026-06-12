#include "pageAccueil.h"
#include "ui_pageAccueil.h"
#include "fontmanager.h"

pageAccueil::pageAccueil(SessionData *data, QWidget *parent) :
    QWidget(parent),
    ui(new Ui::pageAccueil),
    m_data(data)
{
    ui->setupUi(this);

    ui->Titre->setFont(fontmanager::titleFont());
    ui->testCNCButton->setFont(fontmanager::buttonFont());
    ui->testMoteurButton->setFont(fontmanager::buttonFont());

    connect(ui->testCNCButton, &QPushButton::clicked, this, [this]() {
        emit testCNCSelected();
    });

    connect(ui->testMoteurButton, &QPushButton::clicked, this, [this]() {
        emit testMoteurSelected();
    });
}

pageAccueil::~pageAccueil()
{
    delete ui;
}
