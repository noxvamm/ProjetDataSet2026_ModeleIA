#ifndef SUPERVISIONMOTEUR_H
#define SUPERVISIONMOTEUR_H

#include <QWidget>
#include <QTcpSocket>
#include <QUdpSocket>
#include <QTimer>
#include <QFile>
#include <QTextStream>
#include <QVector>
#include <QElapsedTimer>

#include "graphique.h"
#include "sessiondata.h"

namespace Ui {
class supervisionMoteur;
}

class supervisionMoteur : public QWidget
{
    Q_OBJECT

public:
    explicit supervisionMoteur(SessionData *data, QWidget *parent = nullptr);
    ~supervisionMoteur();

signals:
    void retourDemande();

private slots:
    void actualiserTimer();
    void ReceptionDonneesUDP();

private:
    void envoyerDonneesAuServeur();
    void connectESP32();
    void startCSV();
    void stopCSV();
    void resetChart();

    // --- Configuration réseau ESP32 ---
    const QString ESP32_IP = "172.21.1.157";
    const quint16 ESP32_PORT = 9091;

    // --- UI et données ---
    Ui::supervisionMoteur *ui;
    SessionData *m_data;

    // --- Communication ---
    QTcpSocket *m_socket;
    QUdpSocket *m_udpSocket;

    // --- Timer ---
    QTimer *m_timerEnregistrement;
    QElapsedTimer m_testTimer;
    int m_secondesRestantes;

    // --- Graphique ---
    Graphique *m_graphique;

    // --- CSV ---
    QFile m_csvFile;
    QTextStream m_csvStream;

    // --- Données temps réel ---
    long long m_sampleCount;
    double m_elapsedTime;
    double m_lastSoundVal;
    double m_lastVibVal;

    // --- Lissage VIB ---
    static constexpr int VIB_WINDOW = 8;
    QVector<double> m_vibWindow;
};

#endif // SUPERVISIONMOTEUR_H
