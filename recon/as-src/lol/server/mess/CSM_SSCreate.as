class lol.server.mess.CSM_SSCreate extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_SSCreate(s_type, target)
   {
      super();
      this._name = "ss_create";
      this.addProp("target",target);
      this.addProp("s_type",s_type);
   }
}
