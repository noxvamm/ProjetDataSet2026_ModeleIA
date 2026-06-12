#include "graphique.h"
#include <QVBoxLayout>
#include <QPen>
#include <QBrush>
#include <QGraphicsLayout>
#include <QDebug>
#include <cmath>

Graphique::Graphique(QWidget *parent)
    : QWidget(parent),
      m_maxTime(0.0),
      m_autoScroll(true)
{
    // Layout vertical principal
    QVBoxLayout *mainLayout = new QVBoxLayout(this);
    mainLayout->setContentsMargins(0, 0, 0, 0);
    mainLayout->setSpacing(5);

    // Initialisation du Graphique
    m_chart = new QChart();
    m_chart->setBackgroundRoundness(8);
    m_chart->layout()->setContentsMargins(0, 0, 0, 0);
    m_chart->setMargins(QMargins(10, 10, 10, 10));
    m_chart->setBackgroundBrush(QBrush(QColor(245, 245, 247)));

    // Séries
    m_seriesSon = new QLineSeries(this);
    m_seriesSon->setName("Son");
    QPen penSon(QColor(0, 122, 255));
    penSon.setWidth(2);
    m_seriesSon->setPen(penSon);

    m_seriesVibration = new QLineSeries(this);
    m_seriesVibration->setName("Vibration");
    QPen penVib(QColor(255, 59, 48));
    penVib.setWidth(2);
    m_seriesVibration->setPen(penVib);

    m_chart->addSeries(m_seriesSon);
    m_chart->addSeries(m_seriesVibration);

    // Axe X - Temps commun
    m_axisX = new QValueAxis(this);
    m_axisX->setTitleText("Temps (s)");
    m_axisX->setRange(0, 10);
    m_axisX->setLabelFormat("%.1f");
    m_axisX->setGridLineColor(QColor(210, 210, 215));

    // Axe Y Gauche - Amplitude Son
    m_axisYSon = new QValueAxis(this);
    m_axisYSon->setTitleText("Amplitude Son");
    m_axisYSon->setRange(0, 100);
    m_axisYSon->setGridLineColor(QColor(220, 220, 225));
    m_axisYSon->setTitleBrush(QBrush(QColor(0, 122, 255)));
    m_axisYSon->setLabelsBrush(QBrush(QColor(0, 122, 255)));

    // Axe Y Droite - Amplitude Vibration
    m_axisYVib = new QValueAxis(this);
    m_axisYVib->setTitleText("Amplitude Vibration");
    m_axisYVib->setRange(0, 3.3);
    m_axisYVib->setGridLineColor(QColor(220, 220, 225));
    m_axisYVib->setTitleBrush(QBrush(QColor(255, 59, 48)));
    m_axisYVib->setLabelsBrush(QBrush(QColor(255, 59, 48)));

    // Ajout des axes au graphique
    m_chart->addAxis(m_axisX, Qt::AlignBottom);
    m_chart->addAxis(m_axisYSon, Qt::AlignLeft);
    m_chart->addAxis(m_axisYVib, Qt::AlignRight);

    // Liaisons axes/séries
    m_seriesSon->attachAxis(m_axisX);
    m_seriesSon->attachAxis(m_axisYSon);

    m_seriesVibration->attachAxis(m_axisX);
    m_seriesVibration->attachAxis(m_axisYVib);

    // Initialisation de la vue du graphique
    m_chartView = new QChartView(m_chart, this);
    m_chartView->setRenderHint(QPainter::Antialiasing);

    // Activation zoom sélection rectangulaire + déplacement souris
    m_chartView->setRubberBand(QChartView::RectangleRubberBand);
    m_chartView->setDragMode(QGraphicsView::ScrollHandDrag);
    m_chartView->setInteractive(true);

    mainLayout->addWidget(m_chartView);

    // Barre de défilement horizontale moderne
    m_scrollBar = new QScrollBar(Qt::Horizontal, this);
    m_scrollBar->setRange(0, 0); // Pas de scroll nécessaire au début
    m_scrollBar->setFixedHeight(12);
    m_scrollBar->setStyleSheet(
        "QScrollBar:horizontal { height: 12px; background: #E5E5EA; border-radius: 6px; margin: 0px 4px; }"
        "QScrollBar::handle:horizontal { background: #C7C7CC; min-width: 20px; border-radius: 6px; }"
        "QScrollBar::handle:horizontal:hover { background: #8E8E93; }"
        "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; background: none; }"
    );

    mainLayout->addWidget(m_scrollBar);

    // Connexion du défilement
    connect(m_scrollBar, &QScrollBar::valueChanged, this, &Graphique::onScrollBarValueChanged);
}

Graphique::~Graphique()
{
}

void Graphique::ajoutPointSon(double time, double val)
{
    m_seriesSon->append(time, val);
    if (time > m_maxTime) {
        m_maxTime = time;
    }

    // Gestion du scroll
    if (m_maxTime > 10.0) {
        int maxVal = static_cast<int>((m_maxTime - 10.0) * 100);
        m_scrollBar->blockSignals(true);
        m_scrollBar->setRange(0, maxVal);
        if (m_autoScroll) {
            m_scrollBar->setValue(maxVal);
            m_axisX->setRange(m_maxTime - 10.0, m_maxTime);
        }
        m_scrollBar->blockSignals(false);
    }

    updateYScale();
}

void Graphique::ajoutPointVibration(double time, double val)
{
    m_seriesVibration->append(time, val);
    if (time > m_maxTime) {
        m_maxTime = time;
    }

    // Gestion du scroll
    if (m_maxTime > 10.0) {
        int maxVal = static_cast<int>((m_maxTime - 10.0) * 100);
        m_scrollBar->blockSignals(true);
        m_scrollBar->setRange(0, maxVal);
        if (m_autoScroll) {
            m_scrollBar->setValue(maxVal);
            m_axisX->setRange(m_maxTime - 10.0, m_maxTime);
        }
        m_scrollBar->blockSignals(false);
    }

    updateYScale();
}

void Graphique::onScrollBarValueChanged(int value)
{
    double startSec = value / 100.0;
    m_axisX->setRange(startSec, startSec + 10.0);

    // Si on ramène le curseur tout à fait à droite, on réactive le suivi automatique (auto-scroll)
    if (value >= m_scrollBar->maximum() - 5) {
        m_autoScroll = true;
    } else {
        m_autoScroll = false;
    }

    updateYScale();
}

void Graphique::updateYScale()
{
    double minX = m_axisX->min();
    double maxX = m_axisX->max();

    // Recherche du maximum du Son visible à l'écran
    double maxSon = 0.0;
    const auto &pointsSon = m_seriesSon->points();
    for (const QPointF &p : pointsSon) {
        if (p.x() >= minX && p.x() <= maxX) {
            if (p.y() > maxSon) maxSon = p.y();
        }
    }

    // Recherche du maximum de la Vibration visible à l'écran
    double maxVib = 0.0;
    const auto &pointsVib = m_seriesVibration->points();
    for (const QPointF &p : pointsVib) {
        if (p.x() >= minX && p.x() <= maxX) {
            if (p.y() > maxVib) maxVib = p.y();
        }
    }

    // Mise à jour de l'axe Son (gauche)
    if (maxSon > 0.0) {
        m_axisYSon->setRange(0, maxSon * 1.15);
    } else {
        m_axisYSon->setRange(0, 100);
    }

    // Mise à jour de l'axe Vibration (droite)
    if (maxVib > 0.0) {
        // Au moins 1.0 de limite haute pour éviter de zoomer à l'extrême sur du bruit plat
        m_axisYVib->setRange(0, qMax(1.0, maxVib * 1.15));
    } else {
        m_axisYVib->setRange(0, 3.3);
    }
}

void Graphique::reset()
{
    m_seriesSon->clear();
    m_seriesVibration->clear();
    m_maxTime = 0.0;
    m_autoScroll = true;

    m_axisX->setRange(0, 10);
    m_axisYSon->setRange(0, 100);
    m_axisYVib->setRange(0, 3.3);

    m_scrollBar->blockSignals(true);
    m_scrollBar->setRange(0, 0);
    m_scrollBar->setValue(0);
    m_scrollBar->blockSignals(false);
}
