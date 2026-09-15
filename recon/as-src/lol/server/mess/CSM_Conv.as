class lol.server.mess.CSM_Conv extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_Conv(id, op)
   {
      super();
      this._name = "on_conv";
      this.addProp("mob",id);
      this.addProp("op",op);
   }
}
