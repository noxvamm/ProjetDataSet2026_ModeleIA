#include "configurationEnregistrement.h"
#include "ui_configurationEnregistrement.h"

#include "pageAccueil.h"
#include "contexteUsinage.h"
#include "niveauUsure.h"
#include "lancementEnregistrement.h"
#include "configurationMoteur.h"
#include "supervisionMoteur.h"
#include "fontmanager.h"
#include "sessiondata.h"

#include <QShortcut>
#include <cmath>

configurationEnregistrement::configurationEnregistrement(QWidget *parent)
    : QMainWindow(parent)
    , ui(new Ui::configurationEnregistrement)
    , m_data(new SessionData())
{
    ui->setupUi(this);

    // Police du titre et des boutons
    ui->Titre1->setFont(fontmanager::titleFont());
    ui->validerButton->setFont(fontmanager::buttonFont());
    ui->retourButton->setFont(fontmanager::buttonFont());

    // Calcul et affichage dynamique du nombre d'échantillons
    auto updateNbEchantillons = [this]() {
        double duree = ui->dureeEnregistrementSpinBox->value();
        double fs_son = ui->frequenceSonSpinBox->value();
        double fs_vib = ui->frequenceVibrationSpinBox->value();
        long long nb = std::round(duree * (fs_son + fs_vib));
        ui->nbEchantillonsLabel->setText(QString::number(nb));
    };

    connect(ui->dureeEnregistrementSpinBox, &QDoubleSpinBox::valueChanged, this, updateNbEchantillons);
    connect(ui->frequenceSonSpinBox, &QDoubleSpinBox::valueChanged, this, updateNbEchantillons);
    connect(ui->frequenceVibrationSpinBox, &QDoubleSpinBox::valueChanged, this, updateNbEchantillons);

    // Initialisation
    updateNbEchantillons();

    // Raccourcis Page 1
    QShortcut *enter1 = new QShortcut(QKeySequence(Qt::Key_Return), ui->page1);
    enter1->setContext(Qt::WidgetWithChildrenShortcut);
    connect(enter1, &QShortcut::activated, ui->validerButton, &QPushButton::click);

    QShortcut *enter2 = new QShortcut(QKeySequence(Qt::Key_Enter), ui->page1);
    enter2->setContext(Qt::WidgetWithChildrenShortcut);
    connect(enter2, &QShortcut::activated, ui->validerButton, &QPushButton::click);

    // Police globale
    qApp->setFont(fontmanager::globalFont());

    // Instanciation des pages
    m_pageAccueil = new pageAccueil(m_data, this);
    m_configMoteur = new configurationMoteur(m_data, this);
    m_supervisionMoteur = new supervisionMoteur(m_data, this);

    m_page2 = new contexteUsinage(m_data, this);
    m_page3 = new niveauUsure(m_data, this);
    m_page4 = new lancementEnregistrement(m_data, this);

    // Ajout au QStackedWidget
    ui->stackedWidget->addWidget(m_pageAccueil);
    ui->stackedWidget->addWidget(m_configMoteur);
    ui->stackedWidget->addWidget(m_supervisionMoteur);
    ui->stackedWidget->addWidget(m_page2);
    ui->stackedWidget->addWidget(m_page3);
    ui->stackedWidget->addWidget(m_page4);

    // Page d'accueil au démarrage
    ui->stackedWidget->setCurrentWidget(m_pageAccueil);

    // Page d'accueil
    connect(m_pageAccueil, &pageAccueil::testCNCSelected, [this]() {
        ui->stackedWidget->setCurrentWidget(ui->page1);
    });

    connect(m_pageAccueil, &pageAccueil::testMoteurSelected, [this]() {
        ui->stackedWidget->setCurrentWidget(m_configMoteur);
    });

    // Page 1 -> Page 2
    connect(ui->validerButton, &QPushButton::clicked, [this]() {
        m_data->dureeEnregistrement = ui->dureeEnregistrementSpinBox->value();
        m_data->frequenceEchantillonnage = ui->frequenceSonSpinBox->value();
        m_data->frequenceEchantillonnageSon = ui->frequenceSonSpinBox->value();
        m_data->frequenceEchantillonnageVibration = ui->frequenceVibrationSpinBox->value();
        ui->stackedWidget->setCurrentWidget(m_page2);
    });

    connect(ui->retourButton, &QPushButton::clicked, [this]() {
        ui->stackedWidget->setCurrentWidget(m_pageAccueil);
    });

    // Navigation Page 2
    connect(m_page2, &contexteUsinage::validationDemandee, [this]() {
        ui->stackedWidget->setCurrentWidget(m_page3);
    });

    connect(m_page2, &contexteUsinage::retourDemande, [this]() {
        ui->stackedWidget->setCurrentWidget(ui->page1);
    });

    // Navigation Page 3
    connect(m_page3, &niveauUsure::validationDemandee, [this]() {
        ui->stackedWidget->setCurrentWidget(m_page4);
    });

    connect(m_page3, &niveauUsure::retourDemande, [this]() {
        ui->stackedWidget->setCurrentWidget(m_page2);
    });

    // Navigation Page 4
    connect(m_page4, &lancementEnregistrement::retourDemande, [this]() {
        ui->stackedWidget->setCurrentWidget(m_page3);
    });

    // Navigation Configuration Moteur
    connect(m_configMoteur, &configurationMoteur::retourDemande, [this]() {
        ui->stackedWidget->setCurrentWidget(m_pageAccueil);
    });

    connect(m_configMoteur, &configurationMoteur::validationDemandee, [this]() {
        ui->stackedWidget->setCurrentWidget(m_supervisionMoteur);
    });

    // Navigation Supervision Moteur
    connect(m_supervisionMoteur, &supervisionMoteur::retourDemande, [this]() {
        ui->stackedWidget->setCurrentWidget(m_configMoteur);
    });
}

configurationEnregistrement::~configurationEnregistrement()
{
    delete ui;
    delete m_data;
}
