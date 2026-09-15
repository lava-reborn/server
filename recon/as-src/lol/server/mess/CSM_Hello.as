class lol.server.mess.CSM_Hello extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_Hello()
   {
      super();
      this._name = "hello";
      this.addProp("minor",2);
      this.addProp("major",0);
   }
}
