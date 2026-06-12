#ifndef GRAPHIQUE_H
#define GRAPHIQUE_H

#include <QWidget>
#include <QChartView>
#include <QChart>
#include <QLineSeries>
#include <QValueAxis>
#include <QScrollBar>

class Graphique : public QWidget
{
    Q_OBJECT
public:
    explicit Graphique(QWidget *parent = nullptr);
    virtual ~Graphique();

    void ajoutPointSon(double time, double val);
    void ajoutPointVibration(double time, double val);
    void reset();

private slots:
    void onScrollBarValueChanged(int value);

private:
    void updateYScale();

private:
    QChartView *m_chartView;
    QChart *m_chart;
    QLineSeries *m_seriesSon;
    QLineSeries *m_seriesVibration;
    QValueAxis *m_axisX;
    QValueAxis *m_axisYSon;
    QValueAxis *m_axisYVib;
    QScrollBar *m_scrollBar;

    double m_maxTime;
    bool m_autoScroll;
};

#endif // GRAPHIQUE_H
