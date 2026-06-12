QT       += core gui widgets network charts

CONFIG += c++17
TARGET = DataSet2026

SOURCES += \
    configurationEnregistrement.cpp \
    configurationMoteur.cpp \
    contexteUsinage.cpp \
    graphique.cpp \
    lancementEnregistrement.cpp \
    main.cpp \
    niveauUsure.cpp \
    pageAccueil.cpp \
    supervisionMoteur.cpp

HEADERS += \
    configurationEnregistrement.h \
    configurationMoteur.h \
    contexteUsinage.h \
    fontmanager.h \
    graphique.h \
    lancementEnregistrement.h \
    niveauUsure.h \
    pageAccueil.h \
    sessiondata.h \
    supervisionMoteur.h

FORMS += \
    configurationEnregistrement.ui \
    configurationMoteur.ui \
    contexteUsinage.ui \
    lancementEnregistrement.ui \
    niveauUsure.ui \
    pageAccueil.ui \
    supervisionMoteur.ui

# Default rules for deployment.
qnx: target.path = /tmp/$${TARGET}/bin
else: unix:!android: target.path = /opt/$${TARGET}/bin
!isEmpty(target.path): INSTALLS += target
