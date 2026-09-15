class lol.server.mess.CSM_C_Head extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_C_Head(name, desc)
   {
      super();
      this._name = "head";
      this.addProp("reg",desc);
      this.addProp("soc",name);
   }
}
