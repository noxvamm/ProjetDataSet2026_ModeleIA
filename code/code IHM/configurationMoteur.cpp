#include "configurationMoteur.h"
#include "ui_configurationMoteur.h"
#include "fontmanager.h"
#include <QShortcut>

configurationMoteur::configurationMoteur(SessionData *data, QWidget *parent) :
    QWidget(parent),
    ui(new Ui::configurationMoteur),
    m_data(data)
{
    ui->setupUi(this);

    // Polices
    ui->Titre->setFont(fontmanager::titleFont());
    ui->validerButton->setFont(fontmanager::buttonFont());
    ui->retourButton->setFont(fontmanager::buttonFont());

    // Raccourcis
    QShortcut *returnKey = new QShortcut(QKeySequence(Qt::Key_Return), this);
    returnKey->setContext(Qt::WidgetWithChildrenShortcut);
    connect(returnKey, &QShortcut::activated, ui->validerButton, &QPushButton::click);

    QShortcut *enterKey = new QShortcut(QKeySequence(Qt::Key_Enter), this);
    enterKey->setContext(Qt::WidgetWithChildrenShortcut);
    connect(enterKey, &QShortcut::activated, ui->validerButton, &QPushButton::click);

    // Valider
    connect(ui->validerButton, &QPushButton::clicked, this, [this]() {
        m_data->dureeEnregistrement = ui->dureeEnregistrementSpinBox->value();
        m_data->frequenceEchantillonnageSon = ui->frequenceSonSpinBox->value();
        m_data->frequenceEchantillonnageVibration = ui->frequenceVibrationSpinBox->value();
        m_data->frein = ui->freinComboBox->currentText();
        emit validationDemandee();
    });

    // Retour
    connect(ui->retourButton, &QPushButton::clicked, this, [this]() {
        emit retourDemande();
    });
}

configurationMoteur::~configurationMoteur()
{
    delete ui;
}
