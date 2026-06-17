#include "supervisionMoteur.h"
#include "ui_supervisionMoteur.h"
#include "fontmanager.h"

#include <QShortcut>
#include <QHostAddress>
#include <QDir>
#include <QDateTime>
#include <QDebug>
#include <QMessageBox>
#include <QGraphicsLayout>
#include <cmath>

supervisionMoteur::supervisionMoteur(SessionData *data, QWidget *parent) :
    QWidget(parent),
    ui(new Ui::supervisionMoteur),
    m_data(data),
    m_socket(new QTcpSocket(this)),
    m_udpSocket(new QUdpSocket(this)),
    m_timerEnregistrement(new QTimer(this)),
    m_secondesRestantes(0),
    m_graphique(nullptr),
    m_csvFile(),
    m_csvStream(),
    m_sampleCount(0),
    m_elapsedTime(0.0),
    m_lastSoundVal(0.0),
    m_lastVibVal(0.0)
{
    ui->setupUi(this);

    // Polices
    ui->Titre->setFont(fontmanager::titleFont());
    ui->demarrerButton->setFont(fontmanager::buttonFont());
    ui->annulerButton->setFont(fontmanager::buttonFont());
    ui->retourButton->setFont(fontmanager::buttonFont());
    ui->timerLabel->setFont(fontmanager::buttonFont());

    // --- Configuration du Graphique ---
    m_graphique = new Graphique(this);

    // Injection dans le layout
    if (ui->chartContainer->layout() == nullptr) {
        QVBoxLayout *layout = new QVBoxLayout(ui->chartContainer);
        layout->setContentsMargins(0, 0, 0, 0);
        ui->chartContainer->setLayout(layout);
    }
    ui->chartContainer->layout()->addWidget(m_graphique);

    // --- Réception UDP ---
    connect(m_udpSocket, &QUdpSocket::readyRead,
            this, &supervisionMoteur::ReceptionDonneesUDP);

    // Timer d’enregistrement
    connect(m_timerEnregistrement, &QTimer::timeout,
            this, &supervisionMoteur::actualiserTimer);

    // Slider puissance
    connect(ui->puissanceSlider, &QSlider::valueChanged, this, [this](int value) {
        ui->puissanceValueLabel->setText(QString::number(value) + " %");
        m_data->niveauPuissance = value;

        // Si le test est en cours, on envoie immédiatement la nouvelle puissance au serveur
        if (m_timerEnregistrement->isActive()) {
            envoyerDonneesAuServeur();
        }
    });

    // Bouton démarrer
    connect(ui->demarrerButton, &QPushButton::clicked, this, [this]() {
        ui->demarrerButton->setEnabled(false);

        // Préparation de la réception UDP sur le port dédié IHM
        // (sans partage : un conflit de port doit échouer franchement
        // plutôt que voler les paquets du client UDP Python)
        m_udpSocket->close();
        bool ok = m_udpSocket->bind(QHostAddress::AnyIPv4, PORT_ECOUTE_IHM);

        if (!ok) {
            QMessageBox::warning(this, "Erreur UDP",
                                 QString("Impossible d'écouter le port %1.")
                                     .arg(PORT_ECOUTE_IHM));
        }

        resetChart();
        m_testTimer.start();
        startCSV();

        // Envoi de START à l’ESP32 et des paramètres au serveur
        connectESP32();
        envoyerDonneesAuServeur();

        ui->etatValueLabel->setText("En cours");

        m_secondesRestantes = static_cast<int>(m_data->dureeEnregistrement);
        ui->timerLabel->setText(QString::number(m_secondesRestantes) + " s");

        m_timerEnregistrement->start(1000);
    });

    // Bouton annuler
    connect(ui->annulerButton, &QPushButton::clicked, this, [this]() {
        m_timerEnregistrement->stop();
        ui->timerLabel->clear();
        ui->etatValueLabel->setText("En attente");

        // Envoi de STOP à l’ESP32
        QByteArray stopCmd = "STOP";
        m_udpSocket->writeDatagram(stopCmd, QHostAddress(ESP32_IP), ESP32_PORT);

        m_udpSocket->close();
        stopCSV();

        ui->demarrerButton->setEnabled(true);

        if (m_socket->state() == QAbstractSocket::ConnectedState)
            m_socket->disconnectFromHost();
    });

    // Bouton retour
    connect(ui->retourButton, &QPushButton::clicked, this, [this]() {
        emit retourDemande();
    });
}

void supervisionMoteur::actualiserTimer()
{
    m_secondesRestantes--;

    if (m_secondesRestantes >= 0)
        ui->timerLabel->setText(QString::number(m_secondesRestantes) + " s");

    if (m_secondesRestantes <= 0) {
        m_timerEnregistrement->stop();
        ui->etatValueLabel->setText("Terminé");

        // Envoi de STOP à l’ESP32
        QByteArray stopCmd = "STOP";
        m_udpSocket->writeDatagram(stopCmd, QHostAddress(ESP32_IP), ESP32_PORT);

        m_udpSocket->close();
        stopCSV();

        ui->demarrerButton->setEnabled(true);

        if (m_socket->state() == QAbstractSocket::ConnectedState)
            m_socket->disconnectFromHost();
    }
}

void supervisionMoteur::envoyerDonneesAuServeur()
{
    const QString host = "172.21.1.204";
    const quint16 port = 9090;

    m_socket->connectToHost(host, port);

    if (!m_socket->waitForConnected(3000)) {
        ui->etatValueLabel->setText("Erreur connexion serveur");
        return;
    }

    m_socket->write("START\n");
    m_socket->flush();
    m_socket->waitForBytesWritten(1000);

    QString data = m_data->toDataLineMoteur() + "\n";
    m_socket->write(data.toUtf8());
    m_socket->flush();
    m_socket->waitForBytesWritten(3000);

    m_socket->disconnectFromHost();
}

void supervisionMoteur::connectESP32()
{
    // Envoie la commande START à l’ESP32 pour lancer l’acquisition
    QByteArray datagram = "START";
    m_udpSocket->writeDatagram(datagram, QHostAddress(ESP32_IP), ESP32_PORT);
}

void supervisionMoteur::ReceptionDonneesUDP()
{
    // Sécurité : si le test n'est pas actif, on ignore les données
    if (!m_timerEnregistrement->isActive()) {
        while (m_udpSocket->hasPendingDatagrams()) {
            QByteArray dummy;
            dummy.resize(m_udpSocket->pendingDatagramSize());
            m_udpSocket->readDatagram(dummy.data(), dummy.size());
        }
        return;
    }

    while (m_udpSocket->hasPendingDatagrams()) {
        QByteArray datagram;
        datagram.resize(m_udpSocket->pendingDatagramSize());
        m_udpSocket->readDatagram(datagram.data(), datagram.size());

        QString data = QString::fromUtf8(datagram).trimmed();
        QStringList parts = data.split(',');

        if (parts.size() < 3)
            continue;

        QString type = parts[0];
        m_elapsedTime = static_cast<double>(m_testTimer.elapsed()) / 1000.0;

        // SOUND : RMS des 128 échantillons I2S → niveau sonore réel
        if (type == "SOUND") {
            double sumSq = 0;
            int count = 0;
            for (int i = 2; i < parts.size(); i++) {
                bool ok;
                double v = parts[i].toDouble(&ok);
                if (ok) {
                    sumSq += v * v;
                    count++;
                }
            }
            if (count > 0) {
                m_lastSoundVal = std::sqrt(sumSq / count); // RMS
                m_graphique->ajoutPointSon(m_elapsedTime, m_lastSoundVal);
                if (m_csvFile.isOpen())
                    m_csvStream << QString("%1,%2,%3\n")
                                       .arg(m_elapsedTime)
                                       .arg(m_lastSoundVal)
                                       .arg(m_lastVibVal);
                m_sampleCount++;
            }
        }
        // VIB : magnitude vectorielle VX,VY,VZ
        else if (type == "VIB") {
            if (parts.size() > 4) {
                bool okX, okY, okZ;
                double vx = parts[2].toDouble(&okX);
                double vy = parts[3].toDouble(&okY);
                double vz = parts[4].toDouble(&okZ);
                if (okX && okY && okZ) {
                    m_lastVibVal = std::sqrt(vx*vx + vy*vy + vz*vz);
                    m_graphique->ajoutPointVibration(m_elapsedTime, m_lastVibVal);
                    if (m_csvFile.isOpen())
                        m_csvStream << QString("%1,%2,%3\n")
                                           .arg(m_elapsedTime)
                                           .arg(m_lastSoundVal)
                                           .arg(m_lastVibVal);
                    m_sampleCount++;
                }
            }
        }
    }
}

void supervisionMoteur::startCSV()
{
    QDir dir("sessions");
    if (!dir.exists())
        dir.mkpath(".");

    QString timestamp = QDateTime::currentDateTime().toString("yyyyMMdd_HHmmss");
    QString filename = QString("sessions/session_%1.csv").arg(timestamp);

    m_csvFile.setFileName(filename);
    if (m_csvFile.open(QIODevice::WriteOnly | QIODevice::Text)) {
        m_csvStream.setDevice(&m_csvFile);
        m_csvStream << "temps_sec,son,vibration\n";
    }
}

void supervisionMoteur::stopCSV()
{
    if (m_csvFile.isOpen()) {
        m_csvStream.flush();
        m_csvFile.close();
    }
}

void supervisionMoteur::resetChart()
{
    m_graphique->reset();
    m_sampleCount = 0;
    m_elapsedTime = 0.0;
    m_lastSoundVal = 0.0;
    m_lastVibVal = 0.0;
}

supervisionMoteur::~supervisionMoteur()
{
    stopCSV();
    if (m_socket->state() == QAbstractSocket::ConnectedState)
        m_socket->disconnectFromHost();
    delete ui;
}
