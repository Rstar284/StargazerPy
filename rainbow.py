import turtle
t = turtle.Turtle()
s = turtle.Screen()
t.speed(50)
t.width(10)

col = ["violet", "indigo", "blue", "green", "yellow", "orange", "red"]

#s.setup(600, 600)

s.bgcolor("black")

t.right(90)

def semi_circle(col, rad, pos):
    t.color(col)
    t.circle(rad, -180)
    t.up()
    t.setpos(pos, 0)
    t.down()
    t.right(180)
    
for i in range(7):
    semi_circle(col[i], 10*(i + 8), -10*(i +1))
    
t.color("orange")
t.penup()
t.goto(-120, 120)
t.pendown()
t.begin_fill()
t.circle(30)
t.end_fill()

input()
