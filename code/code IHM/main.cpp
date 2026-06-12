#include "configurationEnregistrement.h"
#include <QApplication>

int main(int argc, char *argv[])
{
    QApplication a(argc, argv);
    configurationEnregistrement w;
    w.show();
    return a.exec();
}
