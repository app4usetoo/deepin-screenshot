#include "shapeswidget.h"

#include "utils/calculaterect.h"

#include <QApplication>
#include <QPainter>
#include <QDebug>

const int DRAG_BOUND_RADIUS = 8;

ShapesWidget::ShapesWidget(QWidget *parent)
    : QFrame(parent),
      m_shapesMap(QMap<int ,QString>()),
      m_isMoving(false)
{
    setFocusPolicy(Qt::StrongFocus);
    setMouseTracking(true);
    setAcceptDrops(true);
    installEventFilter(this);
}

ShapesWidget::~ShapesWidget() {

}

void ShapesWidget::setCurrentShape(QString shapeType) {
    m_currentShape = shapeType;
}

void ShapesWidget::mousePressEvent(QMouseEvent *e) {
    m_isRecording = true;
    m_isMoving = false;

    m_currentSelectedDiagPoints.deputyPoint = QPoint(0, 0);
    m_currentSelectedDiagPoints.masterPoint = QPoint(0, 0);

    if (m_pos1 == QPoint(0, 0)) {
        m_pos1 = QPoint(e->x(), e->y());
        qDebug() << "m_pos1:" << m_pos1;
        m_currentDiagPoints.masterPoint = m_pos1;
        m_shapesMap.insert(m_shapesMap.count(), m_currentShape);
    }

    QFrame::mousePressEvent(e);
}

void ShapesWidget::mouseReleaseEvent(QMouseEvent *e) {
    m_isRecording = false;
    if (!m_isMoving) {
        for(int i = 0; i < m_diagPointsList.length(); i++) {
            if (pointOnRect(m_diagPointsList[i], e->pos())) {
                m_currentSelectedDiagPoints = m_diagPointsList[i];
                qDebug() << "#############";
                update();
                break;
            } else {
                continue;
            }
        }
    }

    m_pos2 = QPoint(e->x(), e->y());
    m_currentDiagPoints.deputyPoint = m_pos2;
    m_diagPointsList.append(m_currentDiagPoints);
    m_pos1 =QPoint(0, 0);
    m_pos2 = QPoint(0, 0);
    update();


    QFrame::mouseMoveEvent(e);
}

void ShapesWidget::mouseMoveEvent(QMouseEvent *e) {
    m_pos2 = QPoint(e->x(), e->y());
    m_currentDiagPoints.deputyPoint = m_pos2;

    if (m_isRecording) {
        update();
        m_isMoving = true;
    } else {
        m_currentHoverDiagPoints.masterPoint = QPoint(0, 0);
        m_currentHoverDiagPoints.deputyPoint = QPoint(0, 0);
        if (m_diagPointsList.length() != 0) {
            for(int i = 0; i < m_diagPointsList.length(); i++) {
                if (pointOnRect(m_diagPointsList[i], e->pos())) {

                    m_currentHoverDiagPoints = m_diagPointsList[i];
                    qDebug() << "%%%%%%%%%%%%%%%%%%%%" << m_currentHoverDiagPoints;
                    update();
                    break;

                } else {
                    continue;
                    qDebug() << "!!!!!!!!!!!!!!!";
                }
            }
            update();
        }
    }

    QFrame::mouseMoveEvent(e);
}

void ShapesWidget::paintEvent(QPaintEvent *) {
    QPainter painter(this);

    QPen pen;
    pen.setColor(Qt::red);
    pen.setWidth(1);
    painter.setPen(pen);

    if (m_pos1 != QPoint(0, 0)) {
        QRect curRect = diagPointsRect(m_currentDiagPoints);
        painter.drawRect(curRect);
    }

    for(int i = 0; i < m_diagPointsList.length(); i++) {
        QRect diagRect = diagPointsRect(m_diagPointsList[i]);
        painter.drawRect(diagRect);
    }


    if (m_currentHoverDiagPoints.masterPoint != QPoint(0, 0)) {
        pen.setWidth(1);
        pen.setColor(QColor(0, 0, 255));
        painter.setPen(pen);
        painter.drawRect(diagPointsRect(m_currentHoverDiagPoints));
    }

    if (m_currentSelectedDiagPoints.masterPoint != QPoint(0, 0)) {
        QList<QPoint> tmpPoints = fourPointsOnRect(m_currentSelectedDiagPoints);
        for(int i = 0; i < tmpPoints.length(); i++) {
            painter.drawPixmap(QPoint(tmpPoints[i].x() - DRAG_BOUND_RADIUS,
                                      tmpPoints[i].y() - DRAG_BOUND_RADIUS),
                    QPixmap(":/resources/images/size/resize_handle_big.png"));

            qDebug() << "i =" << i << tmpPoints[i];
        }
    }
}

bool ShapesWidget::eventFilter(QObject *watched, QEvent *event) {
    Q_UNUSED(watched);

    if (event->type() == QEvent::Enter) {
        setCursor(Qt::ArrowCursor);
        qApp->setOverrideCursor(Qt::ArrowCursor);
    }
    return false;
}
