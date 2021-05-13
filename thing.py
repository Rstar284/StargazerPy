# flower drawing =)
import turtle
t = turtle.Turtle()
s = turtle.Screen()

t.width(3)
t.speed(50)

s.bgcolor('teal')

t.color('red')
for i in range(13):
    t.fillcolor('pink')
    t.begin_fill()
    t.up()
    t.goto(-90,-90)
    t.down()
    t.circle(200,70)
    t.end_fill()
    t.fillcolor('purple')
    t.begin_fill()
    t.left(110)
    t.circle(200,70)
    t.end_fill()

input("")
