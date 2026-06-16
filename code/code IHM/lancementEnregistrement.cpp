#include "lancementEnregistrement.h"
#include "ui_lancementEnregistrement.h"
#include "fontmanager.h"

#include <QShortcut>
#include <QHostAddress>
#include <QDebug>

lancementEnregistrement::lancementEnregistrement(SessionData *data, QWidget *parent) :
    QWidget(parent),
    ui(new Ui::lancementEnregistrement),
    m_data(data),
    m_socket(new QTcpSocket(this)),
    m_udpSocket(new QUdpSocket(this)),
    m_timerEnregistrement(new QTimer(this)),
    m_secondesRestantes(0)
{
    ui->setupUi(this);

    // Polices
    ui->Titre4->setFont(fontmanager::titleFont());
    ui->demarrerButton->setFont(fontmanager::buttonFont());
    ui->annulerButton->setFont(fontmanager::buttonFont());
    ui->backButton->setFont(fontmanager::buttonFont());

    // Raccourci ENTER
    QShortcut *return4 = new QShortcut(QKeySequence(Qt::Key_Return), this);
    return4->setContext(Qt::WidgetWithChildrenShortcut);
    connect(return4, &QShortcut::activated, ui->demarrerButton, &QPushButton::click);

    // Timer
    connect(m_timerEnregistrement, &QTimer::timeout,
            this, &lancementEnregistrement::actualiserTimer);

    // Réception UDP
    connect(m_udpSocket, &QUdpSocket::readyRead,
            this, &lancementEnregistrement::ReceptionDonneesUDP);

    // Bouton démarrer
    connect(ui->demarrerButton, &QPushButton::clicked, this, [this]() {

        ui->demarrerButton->setEnabled(false);

        // Bind UDP sur le port dédié IHM (sans partage : un conflit de port
        // doit échouer franchement plutôt que voler les paquets d'un autre process)
        m_udpSocket->close();
        bool ok = m_udpSocket->bind(QHostAddress::AnyIPv4, PORT_ECOUTE_IHM);

        if (!ok) {
            ui->etatValueLabel->setText("Erreur UDP");
            return;
        }

        // Envoi START à l’ESP32 + envoi des paramètres au serveur
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

        // Envoi STOP à l’ESP32
        QByteArray stopCmd = "STOP";
        m_udpSocket->writeDatagram(stopCmd, QHostAddress(ESP32_IP), ESP32_PORT);

        m_udpSocket->close();
        ui->demarrerButton->setEnabled(true);

        if (m_socket->state() == QAbstractSocket::ConnectedState)
            m_socket->disconnectFromHost();
    });

    // Retour
    connect(ui->backButton, &QPushButton::clicked, this, [this]() {
        emit retourDemande();
    });
}

void lancementEnregistrement::actualiserTimer()
{
    m_secondesRestantes--;

    if (m_secondesRestantes >= 0)
        ui->timerLabel->setText(QString::number(m_secondesRestantes) + " s");

    if (m_secondesRestantes <= 0) {
        m_timerEnregistrement->stop();
        ui->etatValueLabel->setText("Terminé");

        // Envoi STOP à l’ESP32
        QByteArray stopCmd = "STOP";
        m_udpSocket->writeDatagram(stopCmd, QHostAddress(ESP32_IP), ESP32_PORT);

        m_udpSocket->close();
        ui->demarrerButton->setEnabled(true);

        if (m_socket->state() == QAbstractSocket::ConnectedState)
            m_socket->disconnectFromHost();
    }
}

void lancementEnregistrement::envoyerDonneesAuServeur()
{
    // ⚠️ IP du PC qui fait tourner serveurTCP_metadonnes_moteur.py — à vérifier le jour J
    const QString host = "172.21.1.197";
    const quint16 port = 9090;

    m_socket->connectToHost(host, port);

    if (!m_socket->waitForConnected(3000)) {
        ui->etatValueLabel->setText("Erreur connexion serveur");
        return;
    }

    m_socket->write("START\n");
    m_socket->flush();
    m_socket->waitForBytesWritten(1000);

    QString data = m_data->toDataLine() + "\n";
    m_socket->write(data.toUtf8());
    m_socket->flush();
    m_socket->waitForBytesWritten(3000);

    m_socket->disconnectFromHost();
}

void lancementEnregistrement::connectESP32()
{
    QByteArray datagram = "START";
    m_udpSocket->writeDatagram(datagram, QHostAddress(ESP32_IP), ESP32_PORT);
}

void lancementEnregistrement::ReceptionDonneesUDP()
{
    while (m_udpSocket->hasPendingDatagrams()) {

        QByteArray datagram;
        datagram.resize(m_udpSocket->pendingDatagramSize());
        m_udpSocket->readDatagram(datagram.data(), datagram.size());

        QString data = QString::fromUtf8(datagram);

        // Traitement futur des données reçues
    }
}

lancementEnregistrement::~lancementEnregistrement()
{
    if (m_socket->state() == QAbstractSocket::ConnectedState)
        m_socket->disconnectFromHost();

    delete ui;
}
