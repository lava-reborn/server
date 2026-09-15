class lol.server.mess.CSM_TS_on_conv extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_TS_on_conv(id, typeID, day)
   {
      super();
      this._name = "on_conv";
      this.addProp("p2",day);
      this.addProp("p1",typeID);
      this.addProp("mob",id);
      this.addProp("op",2);
   }
}
