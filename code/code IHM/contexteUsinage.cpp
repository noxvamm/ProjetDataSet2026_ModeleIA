#include "contexteUsinage.h"
#include "ui_contexteUsinage.h"
#include "fontmanager.h"
#include "configurationEnregistrement.h"
#include <QShortcut>

using namespace std;

contexteUsinage::contexteUsinage(SessionData *data, QWidget *parent) :
    QWidget(parent),
    ui(new Ui::contexteUsinage),
    m_data(data)
{
    ui->setupUi(this);

    // Raccourci clavier Entrée pour valider (contexte restreint à la page)
    QShortcut *return2 = new QShortcut(QKeySequence(Qt::Key_Return), this);
    return2->setContext(Qt::WidgetWithChildrenShortcut);
    connect(return2, &QShortcut::activated, ui->validerButton, &QPushButton::click);

    QShortcut *enter2 = new QShortcut(QKeySequence(Qt::Key_Enter), this);
    enter2->setContext(Qt::WidgetWithChildrenShortcut);
    connect(enter2, &QShortcut::activated, ui->validerButton, &QPushButton::click);

    // Police du titre de la deuxième page
    ui->Titre2->setFont(fontmanager::titleFont());

    ui->validerButton->setFont(fontmanager::buttonFont());
    ui->backButton->setFont(fontmanager::buttonFont());

    // Bouton retour
    connect(ui->backButton, &QPushButton::clicked, this, [this]() {
        emit retourDemande();
    });

    // Bouton valider : remplit les données page 2 et émet un signal
    connect(ui->validerButton, &QPushButton::clicked, this, [this]() {
        m_data->matiere          = ui->comboBoxMatiere->currentText();
        m_data->vitesseCoupe     = ui->lineEditVitesseCoupe->text();
        m_data->vitesseAvance    = ui->lineEditVitesseAvance->text();
        m_data->typeOutil        = ui->comboBoxTypeOutil->currentText();
        m_data->pareurOutil      = ui->comboBoxPareurOutil->currentText();
        m_data->profondeurPasse  = ui->lineEditProfondeurPasse->text();

        emit validationDemandee();
    });
}

contexteUsinage::~contexteUsinage()
{
    delete ui;
}
