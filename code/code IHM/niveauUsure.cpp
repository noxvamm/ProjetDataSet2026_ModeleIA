#include "niveauUsure.h"
#include "ui_niveauUsure.h"
#include "fontmanager.h"
#include "lancementEnregistrement.h"
#include <QShortcut>

using namespace std;

niveauUsure::niveauUsure(SessionData *data, QWidget *parent) :
    QWidget(parent),
    ui(new Ui::niveauUsure),
    m_data(data)
{
    ui->setupUi(this);

    // Raccourci clavier Entrée pour valider (contexte restreint à la page)
    QShortcut *return3 = new QShortcut(QKeySequence(Qt::Key_Return), this);
    return3->setContext(Qt::WidgetWithChildrenShortcut);
    connect(return3, &QShortcut::activated, ui->validerButton, &QPushButton::click);

    QShortcut *enter3 = new QShortcut(QKeySequence(Qt::Key_Enter), this);
    enter3->setContext(Qt::WidgetWithChildrenShortcut);
    connect(enter3, &QShortcut::activated, ui->validerButton, &QPushButton::click);

    // Police du titre de la troisième page
    ui->Titre3->setFont(fontmanager::titleFont());
    ui->validerButton->setFont(fontmanager::buttonFont());
    ui->backButton->setFont(fontmanager::buttonFont());

    // Mise à jour en temps réel du label de pourcentage
    connect(ui->sliderUsure, &QSlider::valueChanged, this, [this](int value) {
        ui->labelUsurePercent->setText(QString::number(value) + " %");
    });

    // Bouton retour
    connect(ui->backButton, &QPushButton::clicked, this, [this]() {
        emit retourDemande();
    });

    // Bouton valider : remplit les données page 3 et émet un signal
    connect(ui->validerButton, &QPushButton::clicked, this, [this]() {
        m_data->noMesure     = ui->lineEditNoMesure->text();
        m_data->totalMesures = ui->lineEditTotalMesures->text();
        m_data->niveauUsure  = QString::number(ui->sliderUsure->value());

        emit validationDemandee();
    });
}

niveauUsure::~niveauUsure()
{
    delete ui;
}
