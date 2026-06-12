#ifndef LANCEMENTENREGISTREMENT_H
#define LANCEMENTENREGISTREMENT_H

#include <QWidget>
#include <QTcpSocket>
#include <QUdpSocket>
#include <QTimer>
#include <QGraphicsScene>
#include <QMessageBox>

#include "sessiondata.h"

namespace Ui {
class lancementEnregistrement;
}

class lancementEnregistrement : public QWidget
{
    Q_OBJECT

public:
    explicit lancementEnregistrement(SessionData *data, QWidget *parent = nullptr);
    ~lancementEnregistrement();

signals:
    void retourDemande();

private slots:
    void actualiserTimer();
    void envoyerDonneesAuServeur();
    void connectESP32();
    void ReceptionDonneesUDP();

private:
    // --- Configuration réseau ESP32 ---
    const QString ESP32_IP = "172.21.1.157";
    const quint16 ESP32_PORT = 9091;

    Ui::lancementEnregistrement *ui;
    SessionData *m_data;

    QTcpSocket *m_socket;
    QUdpSocket *m_udpSocket;
    QTimer *m_timerEnregistrement;

    int m_secondesRestantes;
};

#endif // LANCEMENTENREGISTREMENT_H
